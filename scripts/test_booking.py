
from app.booking.booking_service import (
    get_available_slots,
    book_appointment
)

print("=== CLINIC BOOKING TEST ===")

# 1. Check available slots
slots = get_available_slots()

print(f"Available slots: {len(slots)}")

if not slots:
    print("No available slots found.")
else:
    selected_slot = slots[0]

    print("\nSelected slot:", selected_slot)

    # 2. Book an appointment
    result = book_appointment(
        patient_id="P001",
        slot_id=selected_slot["slot_id"]
    )

    print("\nBooking successful!")
    print(result)

    # 3. Check remaining slots
    remaining = get_available_slots()

    print(f"\nRemaining available slots: {len(remaining)}")

    # 4. Try booking the same slot again
    print("\nTesting duplicate booking prevention:")

    try:
        book_appointment(
            patient_id="P002",
            slot_id=selected_slot["slot_id"]
        )
    except ValueError as error:
        print("Duplicate booking rejected:", error)
