
from app.booking.booking_service import (
    get_available_slots,
    book_appointment,
    cancel_appointment,
    reschedule_appointment,
    get_patient_appointments
)


print("=== AWS CLOUD BOOKING TEST ===")

# 1. Check available slots
slots = get_available_slots()

print("Available AWS slots:", len(slots))

if len(slots) < 2:
    raise RuntimeError(
        "At least two future available slots are required"
    )

old_slot = slots[0]["slot_id"]
new_slot = slots[1]["slot_id"]

# 2. Book appointment
booking = book_appointment("P001", old_slot)

print("\nBooking successful:")
print(booking)

# 3. Test duplicate booking prevention
try:
    book_appointment("P002", old_slot)
    raise AssertionError("Duplicate booking was allowed")
except ValueError:
    print("\nDuplicate booking correctly rejected")

# 4. Test patient ownership
try:
    cancel_appointment(
        "P002", booking["appointment_id"]
    )
    raise AssertionError("Wrong patient cancelled booking")
except ValueError:
    print("Different patient cancellation rejected")

# 5. Reschedule appointment
rescheduled = reschedule_appointment(
    "P001",
    booking["appointment_id"],
    new_slot
)

print("\nRescheduling successful:")
print(rescheduled)

# 6. Cancel new appointment
cancelled = cancel_appointment(
    "P001",
    rescheduled["new_appointment_id"]
)

print("\nCancellation successful:")
print(cancelled)

# 7. Verify both slots were released
available_ids = {
    slot["slot_id"]
    for slot in get_available_slots()
}

assert old_slot in available_ids
assert new_slot in available_ids

history = get_patient_appointments(
    "P001",
    include_history=True
)

print("\nPatient appointment history:", len(history))

print("\nAWS CLOUD BOOKING TEST PASSED")
