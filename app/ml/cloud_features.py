
from app.core.cloud_db import get_cloud_connection


def get_cloud_appointment_features(patient_id, appointment_id):
    """
    Prepare no-show ML features from AWS PostgreSQL.
    Does not run the ML model locally.
    """

    with get_cloud_connection() as conn:

        # 1. Retrieve the active appointment
        appointment = conn.execute(
            """
            SELECT
                a.appointment_id,
                a.patient_id,
                a.created_at,
                (a.created_at AT TIME ZONE 'Europe/London')::date
                    AS booking_date,
                s.date AS appointment_date,
                s.time AS appointment_time,
                s.status AS slot_status,
                s.date -
                    (a.created_at AT TIME ZONE 'Europe/London')::date
                    AS lead_time_days,
                (s.date + s.time) >
                    (CURRENT_TIMESTAMP AT TIME ZONE 'Europe/London')
                    AS is_future,
                r.reminder_planned
            FROM appointments a
            JOIN slots s ON a.slot_id = s.slot_id
            LEFT JOIN appointment_reminders r
                ON a.appointment_id = r.appointment_id
            WHERE a.appointment_id = %s
              AND a.patient_id = %s
              AND a.status = 'booked'
            """,
            (appointment_id, patient_id)
        ).fetchone()

        if not appointment:
            raise ValueError("Active appointment not found")

        if appointment["slot_status"] != "booked":
            raise ValueError("Appointment slot is inconsistent")

        if not appointment["is_future"]:
            raise ValueError("Appointment is not in the future")

        # 2. Check the model's supported input range
        lead_days = appointment["lead_time_days"]

        if not 1 <= lead_days <= 28:
            raise ValueError(
                "Lead time is outside the model's supported range"
            )

        appointment_date = appointment["appointment_date"]
        appointment_time = appointment["appointment_time"]

        if appointment_date.weekday() >= 5:
            raise ValueError("Weekend appointments are unsupported")

        if appointment_time.hour not in (9, 10, 14, 15):
            raise ValueError("Unsupported appointment hour")

        # 3. Check reminder information
        reminder = appointment["reminder_planned"]

        if reminder is None:
            raise ValueError(
                "Reminder information is missing"
            )

        # 4. Retrieve history known before booking
        history = conn.execute(
            """
            SELECT
                COUNT(*) AS previous_appointments,
                COUNT(*) FILTER (
                    WHERE outcome = 'no_show'
                ) AS previous_no_shows
            FROM attendance_history
            WHERE patient_id = %s
              AND appointment_date < %s
              AND recorded_at < %s
            """,
            (
                patient_id,
                appointment["booking_date"],
                appointment["created_at"]
            )
        ).fetchone()

        # For this demo, require known attendance history
        if history["previous_appointments"] == 0:
            raise ValueError(
                "No previous attendance history available"
            )

        # 5. Prepare the six features
        features = {
            "lead_time_days": lead_days,
            "day_of_week": appointment_date.weekday(),
            "appointment_hour": appointment_time.hour,
            "reminder_planned": reminder,
            "previous_appointments": history["previous_appointments"],
            "previous_no_shows": history["previous_no_shows"]
        }

        return features
