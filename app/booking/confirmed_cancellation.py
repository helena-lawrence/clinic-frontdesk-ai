
import uuid

from app.auth.patient_identity import (
    resolve_patient_from_access_token
)

from app.core.cloud_db import get_cloud_connection


def create_cancellation_intent(
    access_token: str,
    appointment_id: str
):
    """
    Create a cancellation preview for an
    authenticated patient's appointment.

    Does not cancel the appointment.
    """

    patient_id = resolve_patient_from_access_token(
        access_token
    )

    if (
        not isinstance(appointment_id, str)
        or not appointment_id.strip()
        or len(appointment_id) > 50
    ):
        raise ValueError("Invalid appointment ID")

    with get_cloud_connection() as conn:

        appointment = conn.execute(
            """
            SELECT
                a.appointment_id,
                a.status,
                s.date,
                s.time,
                d.name AS doctor_name,
                (
                    (s.date + s.time) >
                    (CURRENT_TIMESTAMP
                        AT TIME ZONE 'Europe/London')
                ) AS is_future
            FROM appointments a
            JOIN slots s ON a.slot_id = s.slot_id
            JOIN doctors d ON s.doctor_id = d.doctor_id
            WHERE a.appointment_id = %s
              AND a.patient_id = %s
            """,
            (appointment_id, patient_id)
        ).fetchone()

        if not appointment:
            raise ValueError(
                "Appointment not found for this patient"
            )

        if appointment["status"] != "booked":
            raise ValueError(
                "Only active appointments can be cancelled"
            )

        if not appointment["is_future"]:
            raise ValueError(
                "Cannot cancel a past appointment"
            )

        intent_id = uuid.uuid4()

        result = conn.execute(
            """
            INSERT INTO cancellation_intents (
                intent_id,
                patient_id,
                appointment_id,
                expires_at
            )
            VALUES (
                %s, %s, %s,
                CURRENT_TIMESTAMP + INTERVAL '10 minutes'
            )
            RETURNING expires_at
            """,
            (
                intent_id,
                patient_id,
                appointment_id
            )
        ).fetchone()

    return {
        "intent_id": str(intent_id),
        "appointment_id": appointment_id,
        "doctor_name": appointment["doctor_name"],
        "date": appointment["date"].isoformat(),
        "time": appointment["time"].strftime("%H:%M"),
        "expires_at": result["expires_at"].isoformat(),
        "confirmation_required": True,
        "appointment_cancelled": False
    }


def confirm_cancellation(
    access_token: str,
    intent_id: str,
    confirmation: str
):
    """
    Cancel an appointment after explicit confirmation.

    Authentication and appointment ownership are
    verified before making database changes.
    """

    if confirmation != "CONFIRM CANCEL":
        raise ValueError(
            "Explicit cancellation confirmation required"
        )

    patient_id = resolve_patient_from_access_token(
        access_token
    )

    try:
        validated_intent_id = uuid.UUID(intent_id)
    except (ValueError, TypeError, AttributeError):
        raise ValueError("Invalid cancellation request")

    with get_cloud_connection() as conn:

        # 1. Lock the cancellation request
        intent = conn.execute(
            """
            SELECT
                appointment_id,
                status,
                expires_at > CURRENT_TIMESTAMP
                    AS is_valid
            FROM cancellation_intents
            WHERE intent_id = %s
              AND patient_id = %s
            FOR UPDATE
            """,
            (
                validated_intent_id,
                patient_id
            )
        ).fetchone()

        if not intent:
            raise ValueError(
                "Cancellation request not found"
            )

        if intent["status"] != "pending":
            raise ValueError(
                "Cancellation request already processed"
            )

        if not intent["is_valid"]:
            raise ValueError(
                "Cancellation request expired"
            )

        appointment_id = intent["appointment_id"]

        # 2. Lock the patient's appointment
        appointment = conn.execute(
            """
            SELECT
                a.slot_id,
                a.status,
                s.status AS slot_status,
                (
                    (s.date + s.time) >
                    (CURRENT_TIMESTAMP
                        AT TIME ZONE 'Europe/London')
                ) AS is_future
            FROM appointments a
            JOIN slots s ON a.slot_id = s.slot_id
            WHERE a.appointment_id = %s
              AND a.patient_id = %s
            FOR UPDATE OF a
            """,
            (
                appointment_id,
                patient_id
            )
        ).fetchone()

        if not appointment:
            raise ValueError(
                "Patient appointment not found"
            )

        if appointment["status"] != "booked":
            raise ValueError(
                "Appointment is no longer active"
            )

        if not appointment["is_future"]:
            raise ValueError(
                "Cannot cancel a past appointment"
            )

        if appointment["slot_status"] != "booked":
            raise RuntimeError(
                "Appointment slot state is inconsistent"
            )

        # 3. Cancel the appointment
        updated = conn.execute(
            """
            UPDATE appointments
            SET status = 'cancelled'
            WHERE appointment_id = %s
              AND patient_id = %s
              AND status = 'booked'
            RETURNING appointment_id
            """,
            (
                appointment_id,
                patient_id
            )
        ).fetchone()

        if not updated:
            raise RuntimeError(
                "Appointment cancellation failed"
            )

        # 4. Release the appointment slot
        released = conn.execute(
            """
            UPDATE slots
            SET status = 'available'
            WHERE slot_id = %s
              AND status = 'booked'
            RETURNING slot_id
            """,
            (appointment["slot_id"],)
        ).fetchone()

        if not released:
            raise RuntimeError(
                "Failed to release appointment slot"
            )

        # 5. Mark the request completed
        conn.execute(
            """
            UPDATE cancellation_intents
            SET status = 'confirmed'
            WHERE intent_id = %s
            """,
            (validated_intent_id,)
        )

    return {
        "appointment_id": appointment_id,
        "status": "cancelled",
        "slot_released": True,
        "message": "Appointment cancelled successfully"
    }
