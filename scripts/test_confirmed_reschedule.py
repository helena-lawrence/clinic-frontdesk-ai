
from datetime import datetime
from zoneinfo import ZoneInfo

from scripts.test_cognito_real_login import test_real_login
from app.booking.authenticated_booking import get_my_appointments
from app.booking.booking_service import get_available_slots
from app.booking.confirmed_reschedule import (
    create_reschedule_intent,
    confirm_reschedule
)
from app.core.cloud_db import get_cloud_connection


def main():
    print("=== SECURE RESCHEDULING TEST ===")

    access_token = test_real_login()

    if not access_token:
        raise RuntimeError("Login failed")

    appointments = get_my_appointments(
        access_token
    )["appointments"]

    now = datetime.now(
        ZoneInfo("Europe/London")
    ).replace(tzinfo=None)

    future = [
        a for a in appointments
        if datetime.fromisoformat(
            f"{a['date']}T{a['time']}"
        ) > now
    ]

    if not future:
        raise RuntimeError(
            "No active future appointment. "
            "Book a synthetic future appointment first."
        )

    print("\nYour future appointments:")
    for number, a in enumerate(future, 1):
        print(
            f"{number}. {a['appointment_id']} | "
            f"{a['doctor_name']} | {a['date']} {a['time']}"
        )

    choice = input(
        "\nEnter appointment NUMBER to reschedule: "
    ).strip()

    if not choice.isdigit() or not (
        1 <= int(choice) <= len(future)
    ):
        raise ValueError("Invalid appointment number")

    selected = future[int(choice) - 1]

    available = get_available_slots()

    if not available:
        raise RuntimeError("No future slots available")

    new_slot = available[0]

    print("\nPROPOSED NEW APPOINTMENT")
    print("Doctor:", new_slot["doctor_name"])
    print("Date:", new_slot["date"])
    print("Time:", new_slot["time"])

    intent = create_reschedule_intent(
        access_token,
        selected["appointment_id"],
        new_slot["slot_id"]
    )

    print("\nCURRENT:", intent["old_date"], intent["old_time"])
    print(
        "NEW:",
        intent["new_appointment"]["date"],
        intent["new_appointment"]["time"]
    )
    print("Request expires:", intent["expires_at"])

    assert intent["rescheduled"] is False
    assert intent["confirmation_required"] is True

    # An unconfirmed request must not change the booking.
    try:
        confirm_reschedule(
            access_token,
            intent["intent_id"],
            "NO"
        )
    except ValueError:
        print("PASS: Unconfirmed request rejected")
    else:
        raise AssertionError("Confirmation bypassed")

    confirmation = input(
        "\nType CONFIRM RESCHEDULE to approve: "
    ).strip()

    if confirmation != "CONFIRM RESCHEDULE":
        print("Rescheduling not confirmed. No change made.")
        return

    result = confirm_reschedule(
        access_token,
        intent["intent_id"],
        confirmation
    )

    print("\nRescheduling result:", result)

    # Verify the actual PostgreSQL state.
    with get_cloud_connection() as conn:
        appointment = conn.execute("""
            SELECT slot_id, status
            FROM appointments
            WHERE appointment_id = %s
        """, (result["appointment_id"],)).fetchone()

        old_slot = conn.execute("""
            SELECT status FROM slots WHERE slot_id = %s
        """, (result["old_slot_id"],)).fetchone()

        new_slot_state = conn.execute("""
            SELECT status FROM slots WHERE slot_id = %s
        """, (result["new_slot_id"],)).fetchone()

    assert appointment["slot_id"] == result["new_slot_id"]
    assert appointment["status"] == "booked"
    assert old_slot["status"] == "available"
    assert new_slot_state["status"] == "booked"

    print("PASS: Appointment moved to new slot in AWS")
    print("PASS: Old appointment slot released")

    try:
        confirm_reschedule(
            access_token,
            intent["intent_id"],
            "CONFIRM RESCHEDULE"
        )
    except ValueError:
        print("PASS: Duplicate rescheduling rejected")
    else:
        raise AssertionError("Duplicate confirmation accepted")

    print("\nSECURE RESCHEDULING TEST PASSED")


if __name__ == "__main__":
    main()
