
from datetime import date
from app.core.cloud_db import get_cloud_connection

from app.booking.booking_service import (
    get_available_slots,
    book_appointment,
    cancel_appointment
)

from app.ml.appointment_risk_service import (
    predict_appointment_risk
)


print("=== END-TO-END CLOUD ML TEST ===")

patient_id = "P001"

# 1. Find a suitable future appointment
slots = get_available_slots()

suitable_slots = [
    slot for slot in slots
    if 1 <= (
        date.fromisoformat(slot["date"]) - date.today()
    ).days <= 28
]

if not suitable_slots:
    raise RuntimeError("No suitable appointment slots available")

# 2. Create an appointment in AWS RDS
booking = book_appointment(
    patient_id,
    suitable_slots[0]["slot_id"]
)

appointment_id = booking["appointment_id"]

print("\nAppointment booked:", appointment_id)

try:
    # 3. Record reminder planning in AWS
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

    # 4. Retrieve features and run cloud inference
    result = predict_appointment_risk(
        patient_id=patient_id,
        appointment_id=appointment_id
    )

    print("\nFeatures retrieved from AWS RDS:")
    print(result["features"])

    print("\nPrediction received from AWS Lambda:")
    print(result["prediction"])

    # 5. Validate prediction
    prediction = result["prediction"]

    assert result["appointment_id"] == appointment_id
    assert len(result["features"]) == 6
    assert 0 <= prediction["no_show_score"] <= 1
    assert isinstance(prediction["predicted_no_show"], bool)

    print("\nEND-TO-END CLOUD ML TEST PASSED")

finally:
    # 6. Cancel test appointment
    cancel_appointment(patient_id, appointment_id)
    print("Test appointment cancelled")
