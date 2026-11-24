
import csv
from pathlib import Path
from datetime import date, timedelta

# Find the project root folder
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "synthetic"

DATA_DIR.mkdir(parents=True, exist_ok=True)


def save_csv(filename, columns, records):
    file_path = DATA_DIR / filename

    # Protect existing records from accidental overwriting
    if file_path.exists():
        print(f"Skipped: {filename} already exists")
        return

    with open(file_path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(records)

    print(f"Created: {filename} ({len(records)} records)")


# 1. Synthetic patients
patients = [
    {
        "patient_id": f"P{i:03d}",
        "name": f"Test Patient {i:03d}"
    }
    for i in range(1, 11)
]

save_csv(
    "patients.csv",
    ["patient_id", "name"],
    patients
)


# 2. Synthetic doctors
doctors = [
    {"doctor_id": "D001", "name": "Dr Test A", "specialty": "General Practice"},
    {"doctor_id": "D002", "name": "Dr Test B", "specialty": "General Practice"},
    {"doctor_id": "D003", "name": "Dr Test C", "specialty": "Dermatology"},
    {"doctor_id": "D004", "name": "Dr Test D", "specialty": "Physiotherapy"}
]

save_csv(
    "doctors.csv",
    ["doctor_id", "name", "specialty"],
    doctors
)


# 3. Generate appointment slots for the next 5 weekdays
slots = []
slot_number = 1
current_date = date.today() + timedelta(days=1)
working_days = 0

while working_days < 5:
    if current_date.weekday() < 5:
        for doctor in doctors:
            for time in ["09:00", "10:00", "14:00", "15:00"]:
                slots.append({
                    "slot_id": f"S{slot_number:04d}",
                    "doctor_id": doctor["doctor_id"],
                    "date": current_date.isoformat(),
                    "time": time,
                    "status": "available"
                })
                slot_number += 1

        working_days += 1

    current_date += timedelta(days=1)

save_csv(
    "slots.csv",
    ["slot_id", "doctor_id", "date", "time", "status"],
    slots
)


# 4. Empty appointments file
save_csv(
    "appointments.csv",
    ["appointment_id", "patient_id", "slot_id", "status", "created_at"],
    []
)

print("Synthetic clinic data setup completed.")
