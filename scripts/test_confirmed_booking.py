
from scripts.test_cognito_real_login import test_real_login

from app.booking.booking_service import (
    get_available_slots
)

from app.booking.authenticated_booking import (
    get_my_appointments
)

from app.booking.confirmed_booking import (
    create_booking_intent,
    confirm_booking_intent
)


def main():

    print("=== SECURE BOOKING CONFIRMATION TEST ===")

    # 1. Sign in through AWS Cognito
    access_token = test_real_login()

    if not access_token:
        raise RuntimeError("Cognito login failed")

    print("\nAuthenticated successfully")

    # 2. Retrieve available slots
    slots = get_available_slots()

    if not slots:
        raise RuntimeError(
            "No future slots available for booking"
        )

    selected_slot = slots[0]

    print("\nSelected appointment:")
    print("Doctor:", selected_slot["doctor_name"])
    print("Date:", selected_slot["date"])
    print("Time:", selected_slot["time"])

    # 3. Record active appointments before booking
    before = get_my_appointments(access_token)["count"]

    # 4. Create a temporary booking request
    intent = create_booking_intent(
        access_token,
        selected_slot["slot_id"]
    )

    print("\nBooking preview:")
    print(intent["preview"])
    print("Request expires at:", intent["expires_at"])

    assert intent["booking_created"] is False
    assert intent["confirmation_required"] is True

    # Creating an intent must not create an appointment
    assert (
        get_my_appointments(access_token)["count"]
        == before
    )

    print("\nNo appointment has been booked yet.")

    # 5. Require explicit human confirmation
    confirmation = input(
        "\nType CONFIRM to book this test appointment: "
    ).strip()

    if confirmation != "CONFIRM":
        print("\nBooking not confirmed.")
        print("No appointment created.")
        return

    # 6. Confirm the booking
    result = confirm_booking_intent(
        access_token,
        intent["intent_id"],
        confirmation
    )

    print("\nBooking result:")
    print(result)

    assert result["status"] == "confirmed"
    assert result["booking_created"] is True

    # 7. Verify appointment exists in AWS
    appointments = get_my_appointments(
        access_token
    )["appointments"]

    assert any(
        appointment["appointment_id"]
        == result["appointment_id"]
        for appointment in appointments
    )

    print("\nPASS: Confirmed appointment saved in AWS")

    # 8. Verify the request cannot be reused
    try:
        confirm_booking_intent(
            access_token,
            intent["intent_id"],
            "CONFIRM"
        )
    except ValueError:
        print("PASS: Duplicate confirmation rejected")
    else:
        raise AssertionError(
            "Booking request was confirmed twice"
        )

    print("\nSECURE BOOKING CONFIRMATION TEST PASSED")


if __name__ == "__main__":
    main()
