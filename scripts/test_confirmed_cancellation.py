
from datetime import datetime
from zoneinfo import ZoneInfo

from scripts.test_cognito_real_login import (
    test_real_login
)

from app.booking.authenticated_booking import (
    get_my_appointments
)

from app.booking.confirmed_cancellation import (
    create_cancellation_intent,
    confirm_cancellation
)

from app.core.cloud_db import get_cloud_connection


def main():

    print("=== SECURE CANCELLATION TEST ===")

    # 1. Authenticate through AWS Cognito
    access_token = test_real_login()

    if not access_token:
        raise RuntimeError("Authentication failed")

    # 2. Retrieve this patient's appointments
    appointments = get_my_appointments(
        access_token
    )["appointments"]

    now = datetime.now(
        ZoneInfo("Europe/London")
    )

    future_appointments = []

    for appointment in appointments:

        appointment_datetime = datetime.fromisoformat(
            f"{appointment['date']}T{appointment['time']}"
        ).replace(
            tzinfo=ZoneInfo("Europe/London")
        )

        if appointment_datetime > now:
            future_appointments.append(appointment)

    if not future_appointments:
        raise RuntimeError(
            "No future active appointments found. "
            "A synthetic booking is needed first."
        )

    # 3. Display appointments for the patient
    print("\nYour future appointments:")

    for index, appointment in enumerate(
        future_appointments,
        start=1
    ):
        print(
            f"{index}. "
            f"{appointment['appointment_id']} | "
            f"{appointment['doctor_name']} | "
            f"{appointment['date']} "
            f"{appointment['time']}"
        )

    choice = input(
        "\nEnter appointment number to cancel "
        "(or press Enter to exit): "
    ).strip()

    if not choice:
        print("No cancellation requested")
        return

    if not choice.isdigit():
        raise ValueError("Invalid selection")

    selected_index = int(choice) - 1

    if not 0 <= selected_index < len(future_appointments):
        raise ValueError("Invalid appointment number")

    appointment_id = future_appointments[
        selected_index
    ]["appointment_id"]

    # 4. Generate cancellation preview
    intent = create_cancellation_intent(
        access_token,
        appointment_id
    )

    print("\nCANCELLATION PREVIEW")
    print("Appointment:", intent["appointment_id"])
    print("Doctor:", intent["doctor_name"])
    print("Date:", intent["date"])
    print("Time:", intent["time"])

    assert intent["appointment_cancelled"] is False
    assert intent["confirmation_required"] is True

    # 5. Verify missing confirmation is rejected
    try:
        confirm_cancellation(
            access_token,
            intent["intent_id"],
            "NO"
        )
    except ValueError:
        print("\nPASS: Unconfirmed cancellation rejected")
    else:
        raise AssertionError(
            "Cancellation succeeded without confirmation"
        )

    # 6. Explicit confirmation from the user
    confirmation = input(
        "\nType CONFIRM CANCEL to cancel this appointment: "
    ).strip()

    if confirmation != "CONFIRM CANCEL":
        print("\nCancellation not confirmed")
        return

    # 7. Execute cancellation
    result = confirm_cancellation(
        access_token,
        intent["intent_id"],
        confirmation
    )

    print("\nCancellation result:")
    print(result)

    assert result["status"] == "cancelled"
    assert result["slot_released"] is True

    # 8. Verify the database state
    with get_cloud_connection() as conn:

        row = conn.execute(
            """
            SELECT
                a.status AS appointment_status,
                s.status AS slot_status
            FROM appointments a
            JOIN slots s ON a.slot_id = s.slot_id
            WHERE a.appointment_id = %s
            """,
            (appointment_id,)
        ).fetchone()

    assert row["appointment_status"] == "cancelled"
    assert row["slot_status"] == "available"

    print("PASS: Appointment cancelled in AWS RDS")
    print("PASS: Appointment slot released")

    # 9. Verify the cancellation cannot be repeated
    try:
        confirm_cancellation(
            access_token,
            intent["intent_id"],
            "CONFIRM CANCEL"
        )
    except ValueError:
        print("PASS: Duplicate cancellation rejected")
    else:
        raise AssertionError(
            "Duplicate cancellation was allowed"
        )

    print("\nSECURE CANCELLATION TEST PASSED")


if __name__ == "__main__":
    main()
