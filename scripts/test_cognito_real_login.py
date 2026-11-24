from app.booking.authenticated_booking import (
    get_my_appointments,
    preview_booking
)

from app.booking.booking_service import get_available_slots
import base64
import hashlib
import hmac
import json
import os
import secrets
import webbrowser

from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlencode, urlsplit, parse_qs
from urllib.request import Request, urlopen

from dotenv import load_dotenv

from app.auth.cognito_auth import (
    get_auth_config,
    verify_cognito_access_token
)

from app.auth.patient_identity import (
    resolve_patient_from_access_token
)


# --------------------------------------------------
# Configuration
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

REDIRECT_URI = "http://localhost:8000/auth/callback"


# --------------------------------------------------
# Step 1: Generate PKCE credentials
# --------------------------------------------------

def generate_pkce():

    verifier = secrets.token_urlsafe(64)

    digest = hashlib.sha256(
        verifier.encode("ascii")
    ).digest()

    challenge = base64.urlsafe_b64encode(
        digest
    ).rstrip(b"=").decode("ascii")

    return verifier, challenge


# --------------------------------------------------
# Step 2: Perform real Cognito login
# --------------------------------------------------

def test_real_login():

    print("=== COGNITO REAL LOGIN TEST ===")

    # Load Cognito configuration
    issuer, client_id, _ = get_auth_config()

    domain = os.environ["COGNITO_DOMAIN"].rstrip("/")

    parsed_domain = urlsplit(domain)

    if (
        parsed_domain.scheme != "https"
        or not parsed_domain.netloc
        or parsed_domain.path not in ("", "/")
        or parsed_domain.query
        or parsed_domain.fragment
    ):
        raise ValueError("Invalid Cognito domain URL")

    configured_redirect = os.getenv(
        "COGNITO_REDIRECT_URI"
    )

    if configured_redirect != REDIRECT_URI:
        raise ValueError(
            "Cognito redirect URI mismatch"
        )

    print("Cognito configuration verified")

    # --------------------------------------------------
    # Step 3: Prepare OAuth authorization request
    # --------------------------------------------------

    verifier, challenge = generate_pkce()

    expected_state = secrets.token_urlsafe(32)

    parameters = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "scope": "openid email",
        "state": expected_state,
        "code_challenge": challenge,
        "code_challenge_method": "S256"
    }

    authorize_url = (
        f"{domain}/oauth2/authorize?"
        f"{urlencode(parameters)}"
    )

    callback_data = {}

    # --------------------------------------------------
    # Step 4: Start local callback server
    # --------------------------------------------------

    class CallbackHandler(BaseHTTPRequestHandler):

        def log_message(self, format, *args):
            # Do not log authorization codes or tokens
            pass

        def do_GET(self):

            parsed = urlsplit(self.path)

            if parsed.path != "/auth/callback":
                self.send_error(404)
                return

            params = parse_qs(parsed.query)

            returned_state = params.get(
                "state", [""]
            )[0]

            if not hmac.compare_digest(
                returned_state,
                expected_state
            ):
                callback_data["error"] = (
                    "OAuth state verification failed"
                )

            elif "error" in params:

                callback_data["error"] = (
                    params["error"][0]
                )

            else:

                callback_data["code"] = params.get(
                    "code", [""]
                )[0]

            success = bool(callback_data.get("code"))

            message = (
                "Login received. You can close this tab."
                if success
                else "Authentication failed. Check the terminal."
            )

            body = message.encode("utf-8")

            self.send_response(
                200 if success else 400
            )

            self.send_header(
                "Content-Type",
                "text/plain; charset=utf-8"
            )

            self.send_header(
                "Cache-Control",
                "no-store"
            )

            self.send_header(
                "Referrer-Policy",
                "no-referrer"
            )

            self.send_header(
                "Content-Length",
                str(len(body))
            )

            self.end_headers()

            self.wfile.write(body)

    server = HTTPServer(
        ("127.0.0.1", 8000),
        CallbackHandler
    )

    server.timeout = 600

    try:

        print("\nOpening AWS Cognito login in browser...")

        if not webbrowser.open(authorize_url):
            print(
                "Browser did not open automatically. "
                "Open this URL manually:"
            )
            print(authorize_url)

        # Receive authorization code from Cognito
        server.handle_request()

    finally:
        server.server_close()

    # --------------------------------------------------
    # Step 5: Validate OAuth callback
    # --------------------------------------------------

    if callback_data.get("error"):
        raise RuntimeError(
            callback_data["error"]
        )

    code = callback_data.get("code")

    if not code:
        raise RuntimeError(
            "No authorization code received. "
            "Check Cognito login and callback settings."
        )

    print("Authorization code received")

    # --------------------------------------------------
    # Step 6: Exchange authorization code for token
    # --------------------------------------------------

    token_request = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "code_verifier": verifier
    }

    request = Request(
        f"{domain}/oauth2/token",
        data=urlencode(
            token_request
        ).encode("utf-8"),
        headers={
            "Content-Type":
                "application/x-www-form-urlencoded"
        },
        method="POST"
    )

    print("Exchanging authorization code...")

    with urlopen(request, timeout=20) as response:
        token_data = json.load(response)

    access_token = token_data.get("access_token")

    if not access_token:
        raise RuntimeError(
            "Cognito did not return an access token"
        )

    print("Access token received from AWS Cognito")

    # --------------------------------------------------
    # Step 7: Verify JWT access token
    # --------------------------------------------------

    identity = verify_cognito_access_token(
        access_token
    )

    assert identity["authenticated"] is True
    assert identity["client_id"] == client_id
    assert identity["cognito_sub"]

    print("\nJWT signature verified")
    print("Issuer verified")
    print("App client verified")
    print("Token expiry verified")
    print("Cognito identity verified")

    # --------------------------------------------------
    # Step 8: Resolve Cognito identity using AWS RDS
    # --------------------------------------------------

    print("\nResolving patient identity from AWS RDS...")

    patient_id = resolve_patient_from_access_token(
        access_token
    )

    if patient_id != "P001":
        raise RuntimeError(
            "Cognito user is not mapped to expected "
            "test patient P001"
        )

    print("AWS patient identity resolved:", patient_id)

    print("\nCOGNITO PATIENT IDENTITY TEST PASSED")

    # --------------------------------------------------
    # Step 10: Test authenticated appointment access
    # --------------------------------------------------

    print("\n=== AUTHENTICATED BOOKING ACCESS TEST ===")

    # Retrieve appointments for the verified patient
    result = get_my_appointments(
        access_token
    )

    print("Active appointments:", result["count"])

    assert isinstance(result["appointments"], list)

    print("PASS: Authenticated appointment lookup")

    # Check availability for a booking preview
    slots = get_available_slots()

    if slots:

        slot_id = slots[0]["slot_id"]

        preview = preview_booking(
            access_token,
            slot_id
        )

        print("\nBooking preview:")
        print(preview)

        assert preview["confirmation_required"] is True
        assert preview["booking_created"] is False

        print("PASS: Authenticated booking preview")

    else:
        print(
            "No future available slots. "
            "Booking preview was not tested."
        )

    print("\nAUTHENTICATED BOOKING ACCESS TEST PASSED")


    # --------------------------------------------------
    # Step 9: Final success
    # --------------------------------------------------

    print("\nCOGNITO REAL LOGIN TEST PASSED")
    return access_token


if __name__ == "__main__":
    test_real_login()
