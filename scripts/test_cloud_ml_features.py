
from datetime import date

from app.core.cloud_db import get_cloud_connection
from app.booking.booking_service import (
    get_available_slots,
    book_appointment,
    cancel_appointment
)
from app.ml.cloud_features import (
    get_cloud_appointment_features
)


print("=== AWS CLOUD ML FEATURE TEST ===")

# 1. Find a suitable future slot
slots = get_available_slots()

suitable_slots = [
    slot for slot in slots
    if 1 <= (
        date.fromisoformat(slot["date"]) - date.today()
    ).days <= 28
]

if not suitable_slots:
    raise RuntimeError("No suitable future slots available")

patient_id = "P001"

# 2. Create a synthetic test appointment in AWS
booking = book_appointment(
    patient_id,
    suitable_slots[0]["slot_id"]
)

appointment_id = booking["appointment_id"]

try:
    # 3. Set the test appointment reminder status
    with get_cloud_connection() as conn:
        conn.execute(
            """
            INSERT INTO appointment_reminders
            (appointment_id, reminder_planned)
            VALUES (%s, %s)
            ON CONFLICT (appointment_id) DO NOTHING
            """,
            (appointment_id, 1)
        )

    # 4. Retrieve ML features from AWS
    features = get_cloud_appointment_features(
        patient_id,
        appointment_id
    )

    print("\nML features retrieved from AWS:")

    for name, value in features.items():
        print(f"{name}: {value}")

    # 5. Validate feature preparation
    assert len(features) == 6
    assert features["previous_appointments"] == 6
    assert features["previous_no_shows"] == 0
    assert features["reminder_planned"] == 1

    print("\nAWS CLOUD ML FEATURE TEST PASSED")

finally:
    # Release the booked test slot
    cancel_appointment(patient_id, appointment_id)
    print("Synthetic test appointment cancelled")
