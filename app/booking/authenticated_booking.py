
from app.auth.patient_identity import (
    resolve_patient_from_access_token
)

from app.booking.booking_service import (
    get_patient_appointments
)

from app.core.cloud_db import get_cloud_connection


def get_my_appointments(access_token: str):
    """
    Retrieve appointments belonging to the
    authenticated Cognito patient.

    The patient ID is resolved from AWS RDS,
    never supplied by the caller.
    """

    # 1. Verify Cognito identity
    patient_id = resolve_patient_from_access_token(
        access_token
    )

    # 2. Retrieve only this patient's appointments
    appointments = get_patient_appointments(
        patient_id=patient_id,
        include_history=False
    )

    return {
        "appointments": appointments,
        "count": len(appointments)
    }


def preview_booking(access_token: str, slot_id: str):
    """
    Preview an available appointment slot.

    Requires a verified Cognito identity.
    Does not create a booking.
    """

    # 1. Verify authenticated patient
    resolve_patient_from_access_token(
        access_token
    )

    # 2. Validate requested slot
    if not isinstance(slot_id, str) or not slot_id.strip():
        raise ValueError("Invalid appointment slot")

    if len(slot_id) > 20:
        raise ValueError("Invalid appointment slot")

    # 3. Retrieve slot from AWS PostgreSQL
    with get_cloud_connection() as conn:

        slot = conn.execute(
            """
            SELECT
                s.slot_id,
                d.name AS doctor_name,
                d.specialty,
                s.date,
                s.time,
                s.status,
                (
                    (s.date + s.time) >
                    (CURRENT_TIMESTAMP AT TIME ZONE 'Europe/London')
                ) AS is_future
            FROM slots s
            JOIN doctors d
                ON s.doctor_id = d.doctor_id
            WHERE s.slot_id = %s
            """,
            (slot_id,)
        ).fetchone()

    if slot is None:
        raise ValueError("Appointment slot not found")

    if slot["status"] != "available":
        raise ValueError("Appointment slot unavailable")

    if not slot["is_future"]:
        raise ValueError("Cannot book a past appointment")

    # 4. Return booking preview only
    return {
        "slot_id": slot["slot_id"],
        "doctor_name": slot["doctor_name"],
        "specialty": slot["specialty"],
        "date": slot["date"].isoformat(),
        "time": slot["time"].strftime("%H:%M"),
        "status": "available_at_preview",
        "confirmation_required": True,
        "booking_created": False
    }
