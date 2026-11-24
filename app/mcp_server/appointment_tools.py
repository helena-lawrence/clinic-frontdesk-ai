
import re

from app.core.cloud_db import get_cloud_connection


def register_appointment_tools(mcp):
    """
    Register read-only appointment tools.

    No patient access tokens or patient IDs
    are exposed as MCP tool arguments.
    """

    @mcp.tool()
    def preview_clinic_appointment(slot_id: str) -> dict:
        """
        Preview a clinic appointment slot.

        Returns doctor, specialty, date, time and
        availability. Does not create a booking.
        """

        if (
            not isinstance(slot_id, str)
            or not re.fullmatch(
                r"[A-Za-z0-9_-]{1,20}", slot_id
            )
        ):
            return {
                "available": False,
                "message": "Invalid slot ID",
                "booking_created": False
            }

        with get_cloud_connection() as conn:
            slot = conn.execute(
                """
                SELECT
                    s.slot_id,
                    s.date,
                    s.time,
                    s.status,
                    d.name AS doctor_name,
                    d.specialty,
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
                """,
                (slot_id,)
            ).fetchone()

        if slot is None:
            return {
                "available": False,
                "message": "Slot not found",
                "booking_created": False
            }

        available = (
            slot["status"] == "available"
            and slot["is_future"]
        )

        return {
            "slot_id": slot["slot_id"],
            "doctor_name": slot["doctor_name"],
            "specialty": slot["specialty"],
            "date": slot["date"].isoformat(),
            "time": slot["time"].strftime("%H:%M"),
            "available": available,
            "confirmation_required": True,
            "booking_created": False
        }
