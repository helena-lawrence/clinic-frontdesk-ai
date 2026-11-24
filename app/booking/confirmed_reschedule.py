
import uuid

from app.auth.patient_identity import (
    resolve_patient_from_access_token
)
from app.booking.authenticated_booking import preview_booking
from app.core.cloud_db import get_cloud_connection


def create_reschedule_intent(
    access_token: str,
    appointment_id: str,
    new_slot_id: str
):
    """Preview rescheduling. No appointment is changed."""

    patient_id = resolve_patient_from_access_token(access_token)

    if not isinstance(appointment_id, str) or not (
        0 < len(appointment_id) <= 50
    ):
        raise ValueError("Invalid appointment ID")

    if not isinstance(new_slot_id, str) or not (
        0 < len(new_slot_id) <= 20
    ):
        raise ValueError("Invalid new slot ID")

    # Verify the new slot through our existing service.
    new_preview = preview_booking(access_token, new_slot_id)

    with get_cloud_connection() as conn:
        old = conn.execute("""
            SELECT a.slot_id, a.status,
                   s.status AS slot_status,
                   s.date, s.time,
                   d.name AS doctor_name,
                   (s.date + s.time >
                       (NOW() AT TIME ZONE 'Europe/London')
                   ) AS is_future
            FROM appointments a
            JOIN slots s ON a.slot_id = s.slot_id
            JOIN doctors d ON s.doctor_id = d.doctor_id
            WHERE a.appointment_id = %s
              AND a.patient_id = %s
        """, (appointment_id, patient_id)).fetchone()

        if old is None:
            raise ValueError("Patient appointment not found")

        if old["status"] != "booked":
            raise ValueError("Appointment is not active")

        if old["slot_status"] != "booked":
            raise RuntimeError("Existing slot state is inconsistent")

        if not old["is_future"]:
            raise ValueError("Cannot reschedule a past appointment")

        if old["slot_id"] == new_slot_id:
            raise ValueError("Select a different appointment slot")

        intent_id = uuid.uuid4()

        row = conn.execute("""
            INSERT INTO reschedule_intents (
                intent_id, patient_id, appointment_id,
                old_slot_id, new_slot_id, expires_at
            )
            VALUES (
                %s, %s, %s, %s, %s,
                NOW() + INTERVAL '10 minutes'
            )
            RETURNING expires_at
        """, (
            intent_id, patient_id, appointment_id,
            old["slot_id"], new_slot_id
        )).fetchone()

    return {
        "intent_id": str(intent_id),
        "appointment_id": appointment_id,
        "old_slot_id": old["slot_id"],
        "old_doctor": old["doctor_name"],
        "old_date": old["date"].isoformat(),
        "old_time": old["time"].strftime("%H:%M"),
        "new_appointment": new_preview,
        "expires_at": row["expires_at"].isoformat(),
        "confirmation_required": True,
        "rescheduled": False
    }


def confirm_reschedule(
    access_token: str,
    intent_id: str,
    confirmation: str
):
    """Atomically change an authenticated patient's appointment."""

    if confirmation != "CONFIRM RESCHEDULE":
        raise ValueError("Explicit confirmation required")

    patient_id = resolve_patient_from_access_token(access_token)

    try:
        valid_id = uuid.UUID(intent_id)
    except (ValueError, TypeError, AttributeError):
        raise ValueError("Invalid reschedule request ID")

    with get_cloud_connection() as conn:

        # Lock the temporary request.
        intent = conn.execute("""
            SELECT appointment_id, old_slot_id, new_slot_id,
                   status,
                   expires_at > NOW() AS is_valid
            FROM reschedule_intents
            WHERE intent_id = %s AND patient_id = %s
            FOR UPDATE
        """, (valid_id, patient_id)).fetchone()

        if intent is None:
            raise ValueError("Reschedule request not found")
        if intent["status"] != "pending":
            raise ValueError("Request already processed")
        if not intent["is_valid"]:
            raise ValueError("Request expired. Preview again.")

        appointment_id = intent["appointment_id"]
        old_id = intent["old_slot_id"]
        new_id = intent["new_slot_id"]

        # Lock the owned appointment.
        appointment = conn.execute("""
            SELECT slot_id, status
            FROM appointments
            WHERE appointment_id = %s AND patient_id = %s
            FOR UPDATE
        """, (appointment_id, patient_id)).fetchone()

        if appointment is None:
            raise ValueError("Patient appointment not found")
        if appointment["status"] != "booked":
            raise ValueError("Appointment is no longer active")
        if appointment["slot_id"] != old_id:
            raise ValueError("Appointment has already changed")

        # Lock both slots, using a consistent ordering.
        rows = conn.execute("""
            SELECT slot_id, status,
                   (date + time >
                       (NOW() AT TIME ZONE 'Europe/London')
                   ) AS is_future
            FROM slots
            WHERE slot_id IN (%s, %s)
            ORDER BY slot_id
            FOR UPDATE
        """, (old_id, new_id)).fetchall()

        slots = {row["slot_id"]: row for row in rows}

        if old_id not in slots or new_id not in slots:
            raise ValueError("Appointment slot not found")

        if slots[old_id]["status"] != "booked":
            raise ValueError("Original slot is not booked")
        if not slots[old_id]["is_future"]:
            raise ValueError("Original appointment is in the past")
        if slots[new_id]["status"] != "available":
            raise ValueError("New slot is no longer available")
        if not slots[new_id]["is_future"]:
            raise ValueError("New appointment time is in the past")

        # Reserve the new slot.
        reserved = conn.execute("""
            UPDATE slots SET status = 'booked'
            WHERE slot_id = %s AND status = 'available'
            RETURNING slot_id
        """, (new_id,)).fetchone()

        if reserved is None:
            raise ValueError("New slot became unavailable")

        # Move the existing appointment to the new slot.
        moved = conn.execute("""
            UPDATE appointments
            SET slot_id = %s
            WHERE appointment_id = %s
              AND patient_id = %s
              AND status = 'booked'
              AND slot_id = %s
            RETURNING appointment_id
        """, (
            new_id, appointment_id, patient_id, old_id
        )).fetchone()

        if moved is None:
            raise RuntimeError("Failed to update appointment")

        # Release the old slot.
        released = conn.execute("""
            UPDATE slots SET status = 'available'
            WHERE slot_id = %s AND status = 'booked'
            RETURNING slot_id
        """, (old_id,)).fetchone()

        if released is None:
            raise RuntimeError("Failed to release original slot")

        # Mark this confirmation as used.
        conn.execute("""
            UPDATE reschedule_intents
            SET status = 'confirmed'
            WHERE intent_id = %s
        """, (valid_id,))

    return {
        "appointment_id": appointment_id,
        "old_slot_id": old_id,
        "new_slot_id": new_id,
        "status": "rescheduled",
        "rescheduled": True
    }
