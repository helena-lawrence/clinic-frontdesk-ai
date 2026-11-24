"""Step 11.8.1: non-destructive security smoke tests for the local clinic API.

Run with FastAPI on http://127.0.0.1:8000.
These requests do not log in or alter clinic data.
"""

import sys

import httpx

BASE_URL = "http://127.0.0.1:8000"
SESSION_COOKIE_NAME = "clinic_demo_session"
DUMMY_INTENT_ID = "00000000-0000-4000-8000-000000000000"


# These requests have valid-looking payloads but deliberately NO login cookie.
# Every one must be rejected before any appointment operation runs.
PROTECTED_REQUESTS = [
    ("GET", "/auth/me", None),
    ("GET", "/auth/appointments", None),
    ("GET", "/auth/available-slots", None),
    ("GET", "/auth/csrf", None),
    ("POST", "/auth/booking-intents", {"slot_id": "S0001"}),
    ("POST", "/auth/cancellation-intents", {"appointment_id": "ATEST"}),
    (
        "POST", "/auth/reschedule-intents",
        {"appointment_id": "ATEST", "new_slot_id": "S0002"},
    ),
    ("POST", f"/auth/booking-intents/{DUMMY_INTENT_ID}/confirm", None),
    ("POST", f"/auth/cancellation-intents/{DUMMY_INTENT_ID}/confirm", None),
    ("POST", f"/auth/reschedule-intents/{DUMMY_INTENT_ID}/confirm", None),
]


def require_status(response: httpx.Response, expected: int, name: str) -> None:
    if response.status_code != expected:
        raise AssertionError(
            f"FAIL: {name}: expected HTTP {expected}, "
            f"received {response.status_code}; "
            f"body={response.text[:250]!r}"
        )
    print(f"PASS: {name} (HTTP {expected})")


def main() -> None:
    print("=== CLINIC API SECURITY SMOKE TEST ===")
    print("Tests are read-only or deliberately unauthenticated.\n")

    try:
        with httpx.Client(
            base_url=BASE_URL,
            timeout=10.0,
            trust_env=False,
            follow_redirects=False,
        ) as client:
            response = client.get("/auth/health")
            require_status(response, 200, "FastAPI health")
            if response.json().get("status") != "ok":
                raise AssertionError("FAIL: Health payload is not OK")

            # Anonymous requests must fail, including each mutation endpoint.
            for method, path, body in PROTECTED_REQUESTS:
                response = client.request(method, path, json=body)
                require_status(
                    response,
                    401,
                    f"Anonymous {method} {path}",
                )

            # Random fake cookie must not become an authenticated session.
            client.cookies.set(SESSION_COOKIE_NAME, "fake-session-not-issued-by-server")
            response = client.get("/auth/appointments")
            require_status(response, 401, "Forged session cookie rejected")

            response = client.post(
                "/auth/booking-intents",
                json={"slot_id": "S0001"},
                headers={"X-CSRF-Token": "fake-csrf"},
            )
            require_status(response, 401, "Forged session and CSRF rejected")
            client.cookies.clear()

            # A Cognito callback without a valid code/state must fail.
            response = client.get("/auth/callback")
            require_status(response, 400, "Invalid OAuth callback rejected")

    except httpx.ConnectError:
        print("\nERROR: Cannot reach FastAPI on http://127.0.0.1:8000")
        print("Start clinic_auth_backend with uvicorn in another terminal.")
        sys.exit(1)

    print("\nCLINIC API SECURITY SMOKE TEST PASSED")
    print("No appointment was booked, cancelled, or rescheduled.")


if __name__ == "__main__":
    main()
