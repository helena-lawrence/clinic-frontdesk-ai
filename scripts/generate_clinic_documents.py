
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

OUTPUT_DIR = (
    BASE_DIR / "data" / "synthetic" / "clinic_knowledge"
)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


documents = [
    {
        "document_id": "POL-001",
        "title": "Clinic Opening Hours",
        "category": "opening_hours",
        "content": """
Demo Clinic is open Monday to Friday,
from 9:00 AM to 5:00 PM.

The clinic is closed on Saturdays and Sundays.

Appointments are offered during clinic working hours,
subject to doctor availability.

Patients can ask the front-desk assistant
about available appointment slots.

The assistant must check the booking database
before confirming any appointment availability.
"""
    },
    {
        "document_id": "POL-002",
        "title": "Appointment Booking Policy",
        "category": "appointments",
        "content": """
Patients can request appointments with available doctors.

The booking process includes checking availability,
selecting a suitable appointment slot,
and confirming the booking.

A slot must be available before an appointment
can be booked.

Patients receive an appointment reference
after a successful booking.

The assistant must never confirm an appointment
unless the booking system has successfully
saved the appointment.
"""
    },
    {
        "document_id": "POL-003",
        "title": "Appointment Cancellation Policy",
        "category": "cancellation",
        "content": """
Patients may cancel their appointments.

Demo Clinic requests at least 24 hours'
notice where possible.

Patients may still request cancellation
with less than 24 hours' notice.

The cancellation process requires verification
that the appointment belongs to the patient.

After cancellation, the appointment slot
becomes available for other patients.

The assistant must confirm cancellation only
after the database has been updated successfully.
"""
    },
    {
        "document_id": "POL-004",
        "title": "Appointment Rescheduling Policy",
        "category": "rescheduling",
        "content": """
Patients can request to change an existing appointment.

The new appointment slot must be available.

The booking system verifies the existing appointment
and checks the requested new slot.

After successful rescheduling,
the old slot becomes available.

The system maintains the previous appointment
record as history.

The patient receives a new appointment reference
after successful rescheduling.
"""
    },
    {
        "document_id": "POL-005",
        "title": "Appointment Reminders",
        "category": "reminders",
        "content": """
Demo Clinic supports appointment reminder planning.

Reminder information is associated with
individual appointments.

A reminder may be planned or not planned.

The demonstration system does not automatically
send SMS messages or emails.

Patients should not assume a reminder will arrive.

Patients are responsible for keeping track
of their confirmed appointment dates and times.
"""
    },
    {
        "document_id": "POL-006",
        "title": "Patient Privacy and Data Protection",
        "category": "privacy",
        "content": """
Patient appointment information is private.

Patients should only be allowed to access
their own appointment records.

Identity must be verified before booking,
cancelling or rescheduling appointments
on behalf of a patient.

The AI assistant must not reveal another
patient's appointment information.

Sensitive patient details must not be written
to application logs.

This demonstration uses fictional patient data.
"""
    },
    {
        "document_id": "FAQ-001",
        "title": "Clinic Frequently Asked Questions",
        "category": "faq",
        "content": """
Question: Can I book an appointment online?
Answer: Patients can request available appointments
using the clinic's front-desk assistant.

Question: Can I change my appointment?
Answer: Yes. Patients can request rescheduling
to another available slot.

Question: Can I cancel an appointment?
Answer: Yes. Patients can request cancellation
of their own appointment.

Question: Can the assistant provide a diagnosis?
Answer: No. The assistant provides administrative
support and does not diagnose medical conditions.

Question: What if I have a medical emergency?
Answer: The assistant uses a separate fixed
emergency safety response directing patients
to call 999. Emergency detection must not
depend on the RAG system.
"""
    }
]


def generate_documents():

    for document in documents:

        document_data = {
            "document_id": document["document_id"],
            "title": document["title"],
            "category": document["category"],
            "source": "synthetic_demo_clinic",
            "is_synthetic": True,
            "content": document["content"].strip()
        }

        file_path = OUTPUT_DIR / (
            document["document_id"] + ".json"
        )

        with open(
            file_path,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                document_data,
                file,
                indent=4,
                ensure_ascii=False
            )

        print(f"Created: {file_path.name}")

    print(
        f"\nTotal clinic documents: {len(documents)}"
    )

    print("Clinic knowledge base created successfully!")


if __name__ == "__main__":
    generate_documents()
