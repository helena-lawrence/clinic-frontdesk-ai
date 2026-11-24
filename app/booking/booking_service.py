
import uuid

from datetime import datetime, timezone

from app.core.cloud_db import get_cloud_connection


CLINIC_TIMEZONE = "Europe/London"

FUTURE_SLOT_SQL = """
    (s.date + s.time) >
    (CURRENT_TIMESTAMP AT TIME ZONE 'Europe/London')
"""


def get_available_slots(doctor_id=None):
    """Retrieve future available appointment slots from AWS."""

    query = f"""
        SELECT
            s.slot_id,
            s.doctor_id,
            d.name AS doctor_name,
            s.date,
            s.time
        FROM slots s
        JOIN doctors d ON s.doctor_id = d.doctor_id
        WHERE s.status = 'available'
          AND {FUTURE_SLOT_SQL}
    """

    params = []

    if doctor_id:
        query += " AND s.doctor_id = %s"
        params.append(doctor_id)

    query += " ORDER BY s.date, s.time, s.doctor_id"

    with get_cloud_connection() as conn:
        rows = conn.execute(query, params).fetchall()

    return [
        {
            **row,
            "date": row["date"].isoformat(),
            "time": row["time"].strftime("%H:%M")
        }
        for row in rows
    ]


def book_appointment(patient_id, slot_id):
    """Book an available slot using an AWS database transaction."""

    with get_cloud_connection() as conn:

        patient = conn.execute(
            """
            SELECT patient_id
            FROM patients
            WHERE patient_id = %s
            """,
            (patient_id,)
        ).fetchone()

        if not patient:
            raise ValueError("Patient not found")

        # Lock the selected slot against concurrent bookings
        slot = conn.execute(
            f"""
            SELECT
                s.slot_id,
                s.status,
                s.date,
                s.time,
                d.name AS doctor_name,
                {FUTURE_SLOT_SQL} AS is_future
            FROM slots s
            JOIN doctors d ON s.doctor_id = d.doctor_id
            WHERE s.slot_id = %s
            FOR UPDATE OF s
            """,
            (slot_id,)
        ).fetchone()

        if not slot:
            raise ValueError("Appointment slot not found")

        if slot["status"] != "available":
            raise ValueError("Appointment slot already booked")

        if not slot["is_future"]:
            raise ValueError("Cannot book a past appointment")

        updated = conn.execute(
            """
            UPDATE slots
            SET status = 'booked'
            WHERE slot_id = %s
              AND status = 'available'
            RETURNING slot_id
            """,
            (slot_id,)
        ).fetchone()

        if not updated:
            raise ValueError("Slot is no longer available")

        appointment_id = "A" + uuid.uuid4().hex[:12].upper()

        conn.execute(
            """
            INSERT INTO appointments
            (
                appointment_id,
                patient_id,
                slot_id,
                status,
                created_at
            )
            VALUES (%s, %s, %s, 'booked', %s)
            """,
            (
                appointment_id,
                patient_id,
                slot_id,
                datetime.now(timezone.utc)
            )
        )

        # The connection context commits on success
        # and rolls back automatically on failure.
        return {
            "appointment_id": appointment_id,
            "patient_id": patient_id,
            "doctor": slot["doctor_name"],
            "date": slot["date"].isoformat(),
            "time": slot["time"].strftime("%H:%M"),
            "status": "confirmed"
        }


def cancel_appointment(patient_id, appointment_id):
    """Cancel an appointment and release its slot."""

    with get_cloud_connection() as conn:

        appointment = conn.execute(
            """
            SELECT slot_id
            FROM appointments
            WHERE appointment_id = %s
              AND patient_id = %s
              AND status = 'booked'
            FOR UPDATE
            """,
            (appointment_id, patient_id)
        ).fetchone()

        if not appointment:
            raise ValueError("Active appointment not found")

        conn.execute(
            """
            UPDATE appointments
            SET status = 'cancelled'
            WHERE appointment_id = %s
            """,
            (appointment_id,)
        )

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
            raise RuntimeError("Slot status is inconsistent")

        return {
            "appointment_id": appointment_id,
            "status": "cancelled",
            "message": "Appointment cancelled successfully"
        }


def reschedule_appointment(
    patient_id,
    appointment_id,
    new_slot_id
):
    """Move an appointment while preserving booking history."""

    with get_cloud_connection() as conn:

        appointment = conn.execute(
            """
            SELECT slot_id
            FROM appointments
            WHERE appointment_id = %s
              AND patient_id = %s
              AND status = 'booked'
            FOR UPDATE
            """,
            (appointment_id, patient_id)
        ).fetchone()

        if not appointment:
            raise ValueError("Active appointment not found")

        old_slot_id = appointment["slot_id"]

        if old_slot_id == new_slot_id:
            raise ValueError("New slot must be different")

        new_slot = conn.execute(
            f"""
            SELECT
                s.status,
                s.date,
                s.time,
                d.name AS doctor_name,
                {FUTURE_SLOT_SQL} AS is_future
            FROM slots s
            JOIN doctors d ON s.doctor_id = d.doctor_id
            WHERE s.slot_id = %s
            FOR UPDATE OF s
            """,
            (new_slot_id,)
        ).fetchone()

        if not new_slot:
            raise ValueError("New slot not found")

        if new_slot["status"] != "available":
            raise ValueError("New slot is unavailable")

        if not new_slot["is_future"]:
            raise ValueError("Cannot reschedule into the past")

        # Release the old slot
        released = conn.execute(
            """
            UPDATE slots
            SET status = 'available'
            WHERE slot_id = %s
              AND status = 'booked'
            RETURNING slot_id
            """,
            (old_slot_id,)
        ).fetchone()

        if not released:
            raise RuntimeError("Old slot status is inconsistent")

        # Reserve new slot
        reserved = conn.execute(
            """
            UPDATE slots
            SET status = 'booked'
            WHERE slot_id = %s
              AND status = 'available'
            RETURNING slot_id
            """,
            (new_slot_id,)
        ).fetchone()

        if not reserved:
            raise ValueError("New slot is no longer available")

        # Preserve previous appointment history
        conn.execute(
            """
            UPDATE appointments
            SET status = 'rescheduled'
            WHERE appointment_id = %s
            """,
            (appointment_id,)
        )

        new_appointment_id = "A" + uuid.uuid4().hex[:12].upper()

        conn.execute(
            """
            INSERT INTO appointments
            (
                appointment_id,
                patient_id,
                slot_id,
                status,
                created_at
            )
            VALUES (%s, %s, %s, 'booked', %s)
            """,
            (
                new_appointment_id,
                patient_id,
                new_slot_id,
                datetime.now(timezone.utc)
            )
        )

        return {
            "old_appointment_id": appointment_id,
            "new_appointment_id": new_appointment_id,
            "doctor": new_slot["doctor_name"],
            "date": new_slot["date"].isoformat(),
            "time": new_slot["time"].strftime("%H:%M"),
            "status": "confirmed"
        }


def get_patient_appointments(
    patient_id,
    include_history=False
):
    """Retrieve a patient's bookings from AWS RDS."""

    query = """
        SELECT
            a.appointment_id,
            a.patient_id,
            d.name AS doctor_name,
            d.specialty,
            s.date,
            s.time,
            a.status
        FROM appointments a
        JOIN slots s ON a.slot_id = s.slot_id
        JOIN doctors d ON s.doctor_id = d.doctor_id
        WHERE a.patient_id = %s
    """

    if not include_history:
        query += " AND a.status = 'booked'"

    query += " ORDER BY s.date, s.time"

    with get_cloud_connection() as conn:
        rows = conn.execute(query, (patient_id,)).fetchall()

    return [
        {
            **row,
            "date": row["date"].isoformat(),
            "time": row["time"].strftime("%H:%M")
        }
        for row in rows
    ]
