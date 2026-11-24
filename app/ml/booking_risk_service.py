
from datetime import datetime

from app.booking.booking_service import get_connection
from app.ml.predict import predict_no_show


def predict_appointment_risk(patient_id, appointment_id):
    """
    Fetch appointment data from SQLite,
    prepare ML features and predict no-show risk.
    """

    conn = get_connection()

    try:
        # 1. Find the patient's active appointment
        appointment = conn.execute(
            """
            SELECT
                a.appointment_id,
                a.patient_id,
                a.created_at,
                s.date,
                s.time,
                s.status AS slot_status
            FROM appointments a
            JOIN slots s ON a.slot_id = s.slot_id
            WHERE a.appointment_id = ?
              AND a.patient_id = ?
              AND a.status = 'booked'
            """,
            (appointment_id, patient_id)
        ).fetchone()

        if not appointment:
            raise ValueError("Active appointment not found")

        if appointment["slot_status"] != "booked":
            raise ValueError("Appointment slot is inconsistent")

        # 2. Calculate the appointment date and lead time
        appointment_datetime = datetime.strptime(
            f"{appointment['date']} {appointment['time']}",
            "%Y-%m-%d %H:%M"
        )

        if appointment_datetime <= datetime.now():
            raise ValueError("Appointment is not in the future")

        booking_datetime = datetime.fromisoformat(
            appointment["created_at"]
        )

        # Convert UTC booking time to the computer's local date.
        booking_date = booking_datetime.astimezone().date()

        lead_time_days = (
            appointment_datetime.date() - booking_date
        ).days

        # Current ML model was trained on lead times of 1-28 days
        if not 1 <= lead_time_days <= 28:
            raise ValueError(
                "Appointment lead time is outside the "
                "supported ML range of 1-28 days"
            )

        # 3. Retrieve reminder information
        reminder = conn.execute(
            """
            SELECT reminder_planned
            FROM appointment_reminders
            WHERE appointment_id = ?
            """,
            (appointment_id,)
        ).fetchone()

        if reminder is None:
            raise ValueError(
                "Reminder information is missing. "
                "Prediction is unavailable."
            )

        # 4. Retrieve attendance history known at booking time
        history = conn.execute(
            """
            SELECT
                COUNT(*) AS previous_appointments,
                COALESCE(SUM(
                    CASE
                        WHEN outcome = 'no_show' THEN 1
                        ELSE 0
                    END
                ), 0) AS previous_no_shows
            FROM attendance_history
            WHERE patient_id = ?
              AND appointment_date < ?
              AND recorded_at < ?
            """,
            (
                patient_id,
                booking_date.isoformat(),
                appointment["created_at"]
            )
        ).fetchone()

        if history["previous_appointments"] == 0:
            raise ValueError(
                "No recorded attendance history was available "
                "at booking time. Prediction is unavailable."
            )

        # 5. Prepare the six ML features
        features = {
            "lead_time_days": lead_time_days,
            "day_of_week": appointment_datetime.weekday(),
            "appointment_hour": appointment_datetime.hour,
            "reminder_planned": reminder["reminder_planned"],
            "previous_appointments": history["previous_appointments"],
            "previous_no_shows": history["previous_no_shows"]
        }

        # 6. Run the trained model
        prediction = predict_no_show(features)

        return {
            "appointment_id": appointment_id,
            "appointment_date": appointment["date"],
            "appointment_time": appointment["time"],
            "features": features,
            "prediction": prediction
        }

    finally:
        conn.close()
