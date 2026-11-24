
import csv
import random

from pathlib import Path
from datetime import date, timedelta
from collections import defaultdict

# Project paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "processed"
DATA_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = DATA_DIR / "no_show_training.csv"

# Reproducible synthetic data
rng = random.Random(42)

TOTAL_APPOINTMENTS = 1200
TOTAL_PATIENTS = 180

appointments = []

# 1. Generate historical appointment details
start_date = date.today() - timedelta(days=420)

while len(appointments) < TOTAL_APPOINTMENTS:

    appointment_date = start_date + timedelta(
        days=rng.randint(0, 390)
    )

    # Clinic operates Monday to Friday
    if appointment_date.weekday() >= 5:
        continue

    lead_days = rng.randint(1, 28)
    booking_date = appointment_date - timedelta(
        days=lead_days
    )

    appointments.append({
        "patient_id": f"HP{rng.randint(1, TOTAL_PATIENTS):03d}",
        "booking_date": booking_date.isoformat(),
        "appointment_date": appointment_date.isoformat(),
        "lead_time_days": lead_days,
        "day_of_week": appointment_date.weekday(),
        "appointment_hour": rng.choice([9, 10, 14, 15]),
        "reminder_planned": rng.choice([0, 1, 1, 1])
    })

# Process appointments in chronological order
appointments.sort(
    key=lambda x: (
        x["appointment_date"],
        x["appointment_hour"]
    )
)

# 2. Generate no-show history and outcomes
patient_history = defaultdict(list)
records = []

for index, appointment in enumerate(appointments, start=1):

    patient_id = appointment["patient_id"]
    booking_date = appointment["booking_date"]

    # Only use outcomes already known when booking
    previous = [
        item
        for item in patient_history[patient_id]
        if item["appointment_date"] < booking_date
    ]

    previous_appointments = len(previous)

    previous_no_shows = sum(
        item["no_show"] for item in previous
    )

    previous_no_show_rate = (
        previous_no_shows / previous_appointments
        if previous_appointments else 0
    )

    # Synthetic probability rules
    risk = 0.08

    if appointment["lead_time_days"] >= 15:
        risk += 0.09

    if appointment["reminder_planned"] == 0:
        risk += 0.07

    if appointment["appointment_hour"] == 9:
        risk += 0.05

    risk += 0.24 * previous_no_show_rate

    risk = min(risk, 0.65)

    # Target: 1 = missed, 0 = attended
    no_show = int(rng.random() < risk)

    record = {
        "appointment_id": f"H{index:05d}",
        **appointment,
        "previous_appointments": previous_appointments,
        "previous_no_shows": previous_no_shows,
        "no_show": no_show
    }

    records.append(record)
    patient_history[patient_id].append(record)

# 3. Save training dataset
columns = [
    "appointment_id",
    "patient_id",
    "booking_date",
    "appointment_date",
    "lead_time_days",
    "day_of_week",
    "appointment_hour",
    "reminder_planned",
    "previous_appointments",
    "previous_no_shows",
    "no_show"
]

with open(
    OUTPUT_FILE,
    "w",
    newline="",
    encoding="utf-8"
) as file:

    writer = csv.DictWriter(
        file,
        fieldnames=columns
    )

    writer.writeheader()
    writer.writerows(records)

# 4. Display summary
missed = sum(row["no_show"] for row in records)
attended = len(records) - missed

print("ML training dataset created successfully!")
print(f"Total appointments: {len(records)}")
print(f"Attended: {attended}")
print(f"No-shows: {missed}")
print(f"No-show rate: {missed / len(records):.2%}")
print(f"Saved to: {OUTPUT_FILE}")
