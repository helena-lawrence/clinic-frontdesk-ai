"""Step 11.8.2: real-Cognito / in-process FastAPI / AWS RDS journey test.

Run from project root:
    python -m scripts.test_clinic_patient_journey

Uses ONLY synthetic records. Real AWS RDS mutations occur only after
explicit terminal confirmations. This tests the FastAPI backend endpoints,
not the browser/Streamlit click path or Cognito callback session creation.
"""

import secrets
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from scripts.test_cognito_real_login import test_real_login
from app.auth.patient_identity import resolve_patient_from_access_token
from app.api import clinic_auth_backend as backend
from app.core.cloud_db import get_cloud_connection


def call(client, method, route, expected=200, **kwargs):
    response = client.request(method, route, **kwargs)
    if response.status_code != expected:
        raise AssertionError(
            f"{method} {route}: expected HTTP {expected}, "
            f"got {response.status_code}: {response.text[:350]}"
        )
    return response.json()


def database_state(appointment_id):
    with get_cloud_connection() as conn:
        return conn.execute(
            """
            SELECT a.appointment_id, a.patient_id,
                   a.slot_id, a.status AS appointment_status,
                   s.status AS slot_status
            FROM appointments a
            JOIN slots s ON s.slot_id = a.slot_id
            WHERE a.appointment_id = %s
            """,
            (appointment_id,),
        ).fetchone()


def slot_status(slot_id):
    with get_cloud_connection() as conn:
        row = conn.execute(
            "SELECT status FROM slots WHERE slot_id = %s",
            (slot_id,),
        ).fetchone()
    if row is None:
        raise AssertionError(f"Slot {slot_id} no longer exists")
    return row["status"]


def demand_confirmation(phrase, explanation):
    print(f"\n{explanation}")
    entered = input(f"Type {phrase} to continue (Enter to stop): ").strip()
    if entered != phrase:
        print("Stopped. No further appointment changes were made.")
        return False
    return True


def main():
    print("=== CLINIC PATIENT JOURNEY TEST ===")
    print("Uses synthetic demo data. Requires three explicit confirmations.")
    print("An interrupted run may leave a synthetic booking in AWS RDS.")

    # This established login helper completes Cognito + PKCE and returns
    # the verified access token in memory; it must never print that token.
    token = test_real_login()
    if not token:
        raise RuntimeError("No access token from Cognito login")

    patient_id = resolve_patient_from_access_token(token)
    print("PASS: Real Cognito login and AWS patient mapping")

    # TestClient runs the SAME FastAPI routes in this Python process.
    # Provision a short-lived server-side test session ONLY after JWT
    # validation, matching the structure of the real login backend.
    session_id = secrets.token_urlsafe(40)
    csrf = secrets.token_urlsafe(32)
    with backend._lock:
        backend._sessions[session_id] = (token, time.monotonic() + 1200)
        backend._csrf_tokens[session_id] = csrf

    try:
        with TestClient(backend.app) as client:
            client.cookies.set(backend.SESSION_COOKIE, session_id)
            headers = {"X-CSRF-Token": csrf}

            me = call(client, "GET", "/auth/me")
            assert me["authenticated"] is True
            assert me["patient_id"] == patient_id
            print("PASS: Authenticated FastAPI session")

            initial = call(client, "GET", "/auth/appointments")
            print("Existing active appointments:", initial["count"])

            available = call(client, "GET", "/auth/available-slots")
            cutoff = (datetime.now(ZoneInfo("Europe/London"))
                      + timedelta(minutes=45)).replace(tzinfo=None)
            future = [
                s for s in available["slots"]
                if datetime.fromisoformat(f"{s['date']}T{s['time']}") > cutoff
            ]
            if len(future) < 2:
                raise RuntimeError(
                    "Need at least two available synthetic slots more than "
                    "45 minutes in the future. Add future test slots first."
                )

            first, second = future[:2]
            print("\nOriginal slot:", first["slot_id"], first["doctor_name"],
                  first["date"], first["time"])
            print("New slot:", second["slot_id"], second["doctor_name"],
                  second["date"], second["time"])

            # A signed-in user without CSRF must still be rejected.
            call(client, "POST", "/auth/booking-intents",
                 expected=403, json={"slot_id": first["slot_id"]})
            print("PASS: Authenticated write without CSRF rejected")

            booking = call(
                client, "POST", "/auth/booking-intents",
                headers=headers, json={"slot_id": first["slot_id"]},
            )
            assert booking["booking_created"] is False
            assert booking["confirmation_required"] is True
            print("Booking preview:", booking["preview"])
            print("PASS: Booking preview created without booking")

            if not demand_confirmation(
                "CONFIRM BOOKING",
                "Step 1/3: create this synthetic booking in AWS RDS?",
            ):
                return

            booked = call(
                client, "POST",
                f"/auth/booking-intents/{booking['intent_id']}/confirm",
                headers=headers,
            )
            appointment_id = booked["appointment_id"]
            state = database_state(appointment_id)
            assert state and state["patient_id"] == patient_id
            assert state["slot_id"] == first["slot_id"]
            assert state["appointment_status"] == "booked"
            assert state["slot_status"] == "booked"
            print("PASS: Booking saved in AWS RDS:", appointment_id)

            call(
                client, "POST",
                f"/auth/booking-intents/{booking['intent_id']}/confirm",
                headers=headers, expected=409,
            )
            print("PASS: Duplicate booking rejected")

            # Preview the move before asking to authorise the change.
            move = call(
                client, "POST", "/auth/reschedule-intents",
                headers=headers,
                json={"appointment_id": appointment_id,
                      "new_slot_id": second["slot_id"]},
            )
            assert move["rescheduled"] is False
            assert database_state(appointment_id)["slot_id"] == first["slot_id"]
            print("PASS: Reschedule preview did not change appointment")

            if not demand_confirmation(
                "CONFIRM RESCHEDULE",
                f"Step 2/3: move {appointment_id} to {second['date']} "
                f"at {second['time']}?",
            ):
                print("A synthetic booking remains; cancel it in Streamlit if needed.")
                return

            moved = call(
                client, "POST",
                f"/auth/reschedule-intents/{move['intent_id']}/confirm",
                headers=headers,
            )
            assert moved["rescheduled"] is True
            state = database_state(appointment_id)
            assert state["slot_id"] == second["slot_id"]
            assert state["appointment_status"] == "booked"
            assert slot_status(first["slot_id"]) == "available"
            assert slot_status(second["slot_id"]) == "booked"
            print("PASS: Appointment moved; old slot released")

            call(
                client, "POST",
                f"/auth/reschedule-intents/{move['intent_id']}/confirm",
                headers=headers, expected=409,
            )
            print("PASS: Duplicate rescheduling rejected")

            cancellation = call(
                client, "POST", "/auth/cancellation-intents",
                headers=headers, json={"appointment_id": appointment_id},
            )
            assert cancellation["appointment_cancelled"] is False
            assert database_state(appointment_id)["appointment_status"] == "booked"
            print("PASS: Cancellation preview did not change appointment")

            if not demand_confirmation(
                "CONFIRM CANCEL",
                f"Step 3/3: cancel synthetic appointment {appointment_id}?",
            ):
                print("A synthetic booking remains; cancel it in Streamlit if needed.")
                return

            cancelled = call(
                client, "POST",
                f"/auth/cancellation-intents/{cancellation['intent_id']}/confirm",
                headers=headers,
            )
            assert cancelled["status"] == "cancelled"
            assert database_state(appointment_id)["appointment_status"] == "cancelled"
            assert slot_status(first["slot_id"]) == "available"
            assert slot_status(second["slot_id"]) == "available"
            print("PASS: Cancellation saved; both slots available")

            call(
                client, "POST",
                f"/auth/cancellation-intents/{cancellation['intent_id']}/confirm",
                headers=headers, expected=409,
            )
            print("PASS: Duplicate cancellation rejected")

            print("\nCLINIC PATIENT JOURNEY TEST PASSED")
            print("The created demo appointment was cancelled and both slots released.")

    finally:
        with backend._lock:
            backend._sessions.pop(session_id, None)
            backend._csrf_tokens.pop(session_id, None)


if __name__ == "__main__":
    main()

