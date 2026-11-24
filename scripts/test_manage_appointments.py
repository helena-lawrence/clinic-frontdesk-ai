
from app.booking.booking_service import (
    get_available_slots,
    book_appointment,
    cancel_appointment,
    reschedule_appointment,
    get_connection
)

print("=== APPOINTMENT MANAGEMENT TEST ===")

# Find two free slots
slots = get_available_slots()

if len(slots) < 2:
    raise RuntimeError("At least 2 available slots are required")

old_slot_id = slots[0]["slot_id"]
new_slot_id = slots[1]["slot_id"]

# Test 1: Book appointment
booking = book_appointment("P001", old_slot_id)
appointment_id = booking["appointment_id"]

print("\n1. Booking successful:")
print(booking)

# Test 2: Prevent another patient from cancelling
try:
    cancel_appointment("P002", appointment_id)
    raise AssertionError("Unauthorised cancellation succeeded")
except ValueError:
    print("\n2. Different patient cannot cancel appointment")

# Test 3: Reschedule appointment
result = reschedule_appointment(
    patient_id="P001",
    appointment_id=appointment_id,
    new_slot_id=new_slot_id
)

print("\n3. Rescheduling successful:")
print(result)

new_appointment_id = result["new_appointment_id"]

# Test 4: Cancel the rescheduled appointment
cancel_result = cancel_appointment(
    patient_id="P001",
    appointment_id=new_appointment_id
)

print("\n4. Cancellation successful:")
print(cancel_result)

# Test 5: Check database records
conn = get_connection()

try:
    old_status = conn.execute(
        "SELECT status FROM slots WHERE slot_id = ?",
        (old_slot_id,)
    ).fetchone()["status"]

    new_status = conn.execute(
        "SELECT status FROM slots WHERE slot_id = ?",
        (new_slot_id,)
    ).fetchone()["status"]

    original_appointment_status = conn.execute(
        "SELECT status FROM appointments WHERE appointment_id = ?",
        (appointment_id,)
    ).fetchone()["status"]

    new_appointment_status = conn.execute(
        "SELECT status FROM appointments WHERE appointment_id = ?",
        (new_appointment_id,)
    ).fetchone()["status"]

finally:
    conn.close()

assert old_status == "available"
assert new_status == "available"
assert original_appointment_status == "rescheduled"
assert new_appointment_status == "cancelled"

print("\n5. Database validation passed")
print("Old slot:", old_status)
print("New slot:", new_status)
print("Original appointment:", original_appointment_status)
print("New appointment:", new_appointment_status)

print("\nALL TESTS PASSED")
