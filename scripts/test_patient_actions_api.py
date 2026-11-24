
from fastapi.testclient import TestClient

from app.api.patient_actions_api import app
from app.booking.booking_service import get_available_slots
from scripts.test_cognito_real_login import test_real_login


def main():

    print("=== FASTAPI TRUSTED ACTION TEST ===")

    with TestClient(app) as client:

        # 1. Check API health
        response = client.get("/health")

        assert response.status_code == 200
        print("PASS: FastAPI health check")

        # 2. Reject anonymous patients
        response = client.get("/patient/appointments")

        assert response.status_code == 401
        print("PASS: Anonymous access rejected")

        # 3. Reject invalid JWT
        response = client.get(
            "/patient/appointments",
            headers={
                "Authorization": "Bearer invalid-token"
            }
        )

        assert response.status_code == 401
        print("PASS: Invalid JWT rejected")

        # 4. Authenticate through real AWS Cognito
        access_token = test_real_login()

        if not access_token:
            raise RuntimeError("Cognito login failed")

        headers = {
            "Authorization": f"Bearer {access_token}"
        }

        # 5. Retrieve authenticated appointments
        response = client.get(
            "/patient/appointments",
            headers=headers
        )

        assert response.status_code == 200, (
            response.status_code
        )

        data = response.json()

        assert isinstance(data["appointments"], list)

        print("PASS: Authenticated patient lookup")
        print("Appointment count:", data["count"])

        before_count = data["count"]

        # 6. Create booking intent only
        slots = get_available_slots()

        if not slots:
            raise RuntimeError(
                "No future available slots for preview test"
            )

        response = client.post(
            "/patient/booking-intents",
            headers=headers,
            json={
                "slot_id": slots[0]["slot_id"]
            }
        )

        assert response.status_code == 200, (
            f"{response.status_code}: "
            f"{response.text}"
        )

        intent = response.json()

        assert intent["booking_created"] is False
        assert intent["confirmation_required"] is True

        print("PASS: Booking preview created")

        # 7. Incorrect confirmation must be rejected
        response = client.post(
            "/patient/booking-intents/"
            f"{intent['intent_id']}/confirm",
            headers=headers,
            json={
                "confirmation": "NO"
            }
        )

        assert response.status_code == 422
        print("PASS: Invalid confirmation rejected")

        # 8. Check no appointment was created
        response = client.get(
            "/patient/appointments",
            headers=headers
        )

        assert response.status_code == 200

        after_count = response.json()["count"]

        assert after_count == before_count

        print("PASS: No appointment created")

    print("\nFASTAPI TRUSTED ACTION TEST PASSED")


if __name__ == "__main__":
    main()
