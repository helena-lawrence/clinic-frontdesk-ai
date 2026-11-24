
import uuid

from app.auth.patient_identity import (
    resolve_patient_from_access_token
)

from app.booking.authenticated_booking import (
    preview_booking
)

from app.core.cloud_db import get_cloud_connection


def create_booking_intent(access_token: str, slot_id: str):
    """
    Create a temporary booking request.

    Does not book or reserve the appointment.
    """

    patient_id = resolve_patient_from_access_token(
        access_token
    )

    preview = preview_booking(
        access_token,
        slot_id
    )

    intent_id = uuid.uuid4()

    with get_cloud_connection() as conn:

        row = conn.execute(
            """
            INSERT INTO booking_intents (
                intent_id,
                patient_id,
                slot_id,
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
                slot_id
            )
        ).fetchone()

    return {
        "intent_id": str(intent_id),
        "preview": preview,
        "expires_at": row["expires_at"].isoformat(),
        "confirmation_required": True,
        "booking_created": False
    }


def confirm_booking_intent(
    access_token: str,
    intent_id: str,
    confirmation: str
):
    """
    Confirm a booking request after explicit
    user approval in the trusted application.

    All database changes happen atomically.
    """

    if confirmation != "CONFIRM":
        raise ValueError(
            "Explicit booking confirmation is required"
        )

    patient_id = resolve_patient_from_access_token(
        access_token
    )

    try:
        validated_intent_id = uuid.UUID(intent_id)
    except (ValueError, TypeError, AttributeError):
        raise ValueError("Invalid booking request ID")

    with get_cloud_connection() as conn:

        # 1. Lock the booking request
        intent = conn.execute(
            """
            SELECT
                slot_id,
                status,
                expires_at > CURRENT_TIMESTAMP
                    AS is_valid
            FROM booking_intents
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
            raise ValueError("Booking request not found")

        if intent["status"] != "pending":
            raise ValueError(
                "Booking request already processed"
            )

        if not intent["is_valid"]:
            raise ValueError(
                "Booking request expired. Preview again."
            )

        slot_id = intent["slot_id"]

        # 2. Lock and recheck the appointment slot
        slot = conn.execute(
            """
            SELECT
                s.slot_id,
                s.date,
                s.time,
                s.status,
                d.name AS doctor_name,
                (
                    (s.date + s.time) >
                    (
                        CURRENT_TIMESTAMP
                        AT TIME ZONE 'Europe/London'
                    )
                ) AS is_future
            FROM slots s
            JOIN doctors d
                ON s.doctor_id = d.doctor_id
            WHERE s.slot_id = %s
            FOR UPDATE OF s
            """,
            (slot_id,)
        ).fetchone()

        if not slot:
            raise ValueError("Appointment slot not found")

        if slot["status"] != "available":
            raise ValueError(
                "Appointment slot is no longer available"
            )

        if not slot["is_future"]:
            raise ValueError(
                "Cannot book an appointment in the past"
            )

        # 3. Reserve the appointment slot
        reserved = conn.execute(
            """
            UPDATE slots
            SET status = 'booked'
            WHERE slot_id = %s
              AND status = 'available'
            RETURNING slot_id
            """,
            (slot_id,)
        ).fetchone()

        if not reserved:
            raise ValueError(
                "Appointment slot is no longer available"
            )

        # 4. Create the actual appointment
        appointment_id = (
            "A" + uuid.uuid4().hex[:12].upper()
        )

        conn.execute(
            """
            INSERT INTO appointments (
                appointment_id,
                patient_id,
                slot_id,
                status
            )
            VALUES (%s, %s, %s, 'booked')
            """,
            (
                appointment_id,
                patient_id,
                slot_id
            )
        )

        # 5. Mark the confirmation as completed
        conn.execute(
            """
            UPDATE booking_intents
            SET status = 'confirmed',
                appointment_id = %s
            WHERE intent_id = %s
            """,
            (
                appointment_id,
                validated_intent_id
            )
        )

        # All changes commit together on success.
        return {
            "appointment_id": appointment_id,
            "doctor_name": slot["doctor_name"],
            "date": slot["date"].isoformat(),
            "time": slot["time"].strftime("%H:%M"),
            "status": "confirmed",
            "booking_created": True
        }
