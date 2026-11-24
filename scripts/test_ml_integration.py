
from datetime import date, datetime

from app.booking.booking_service import (
    get_connection,
    get_available_slots,
    book_appointment
)

from app.ml.booking_risk_service import (
    predict_appointment_risk
)


print("=== ML + SQLITE INTEGRATION TEST ===")

patient_id = "P001"

# Find an existing future booking for P001
conn = get_connection()

try:
    bookings = conn.execute(
        """
        SELECT
            a.appointment_id,
            a.created_at,
            s.date,
            s.time
        FROM appointments a
        JOIN slots s ON a.slot_id = s.slot_id
        WHERE a.patient_id = ?
          AND a.status = 'booked'
        ORDER BY a.created_at DESC
        """,
        (patient_id,)
    ).fetchall()
finally:
    conn.close()

appointment_id = None

for booking in bookings:
    appointment_datetime = datetime.strptime(
        f"{booking['date']} {booking['time']}",
        "%Y-%m-%d %H:%M"
    )

    booking_date = datetime.fromisoformat(
        booking["created_at"]
    ).astimezone().date()

    lead_days = (appointment_datetime.date() - booking_date).days

    if appointment_datetime > datetime.now() and 1 <= lead_days <= 28:
        appointment_id = booking["appointment_id"]
        break


# Create a synthetic test booking only if needed
if appointment_id is None:

    available_slots = get_available_slots()

    suitable_slots = [
        slot for slot in available_slots
        if 1 <= (
            date.fromisoformat(slot["date"]) - date.today()
        ).days <= 28
    ]

    if not suitable_slots:
        raise RuntimeError("No suitable future slots available")

    booking = book_appointment(
        patient_id,
        suitable_slots[0]["slot_id"]
    )

    appointment_id = booking["appointment_id"]

    print("Created a new synthetic test booking")


# Record that no reminder is planned for this test booking.
# 0 = no reminder planned. No message is sent.
conn = get_connection()

try:
    with conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO appointment_reminders
            (appointment_id, reminder_planned)
            VALUES (?, ?)
            """,
            (appointment_id, 0)
        )
finally:
    conn.close()


# Run integrated ML prediction
result = predict_appointment_risk(
    patient_id=patient_id,
    appointment_id=appointment_id
)

print("\nAppointment ID:", result["appointment_id"])

print("\nAutomatically prepared ML features:")
for feature, value in result["features"].items():
    print(f"{feature}: {value}")

print("\nML Prediction:")
print(result["prediction"])

assert 0 <= result["prediction"]["no_show_score"] <= 1

print("\nML + SQLITE INTEGRATION TEST PASSED")
