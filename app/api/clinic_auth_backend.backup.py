"""Local-only Cognito sign-in bridge for the Clinic Front-Desk demo.

Runs at http://localhost:8000. Uses the existing public Cognito app client
with Authorization Code + PKCE. Access tokens remain in this Python process.
Do not expose this service to the network or use it unchanged in production.
"""

import base64
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from dotenv import load_dotenv
from fastapi import Cookie, FastAPI, HTTPException, Query, Header
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

from app.auth.cognito_auth import get_auth_config
from app.auth.patient_identity import resolve_patient_from_access_token
from app.booking.authenticated_booking import get_my_appointments
from app.core.cloud_db import get_cloud_connection
from app.booking.confirmed_booking import create_booking_intent, confirm_booking_intent
from app.booking.confirmed_cancellation import create_cancellation_intent, confirm_cancellation
from app.booking.confirmed_reschedule import create_reschedule_intent, confirm_reschedule


app = FastAPI(title="Clinic Cognito Login Bridge", docs_url=None, redoc_url=None)

COGNITO_DOMAIN = os.environ["COGNITO_DOMAIN"].rstrip("/")
REDIRECT_URI = "http://localhost:8000/auth/callback"
STREAMLIT_URL = "http://localhost:8502/"
STATE_COOKIE = "clinic_demo_oauth_state"
SESSION_COOKIE = "clinic_demo_session"

parsed = urlsplit(COGNITO_DOMAIN)
if parsed.scheme != "https" or not parsed.netloc or parsed.path or parsed.query or parsed.fragment:
    raise RuntimeError("COGNITO_DOMAIN must be an HTTPS domain without a path")

if os.getenv("COGNITO_REDIRECT_URI") != REDIRECT_URI:
    raise RuntimeError(
        "COGNITO_REDIRECT_URI must equal http://localhost:8000/auth/callback"
    )

_issuer, CLIENT_ID, _unused = get_auth_config()

# These dictionaries live only in the local backend process. Restarting it
# deliberately logs everyone out. Values are never sent to Streamlit or LLMs.
_pending: dict[str, tuple[str, float]] = {}
_sessions: dict[str, tuple[str, float]] = {}
_csrf_tokens: dict[str, str] = {}
_lock = threading.Lock()


def _pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def _clean_expired() -> None:
    now = time.monotonic()
    with _lock:
        for cache in (_pending, _sessions):
            for key in [k for k, (_, deadline) in cache.items() if deadline < now]:
                del cache[key]
                if cache is _sessions:
                    _csrf_tokens.pop(key, None)


@app.get("/auth/health")
def health():
    return {"status": "ok"}


@app.get("/auth/start")
def start_login():
    _clean_expired()
    state = secrets.token_urlsafe(32)
    verifier, challenge = _pkce()
    with _lock:
        _pending[state] = (verifier, time.monotonic() + 600)

    parameters = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": "openid email",
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    response = RedirectResponse(
        url=f"{COGNITO_DOMAIN}/oauth2/authorize?{urlencode(parameters)}",
        status_code=302,
    )
    # Lax allows this cookie on the cross-site, top-level callback navigation.
    response.set_cookie(
        key=STATE_COOKIE,
        value=state,
        max_age=600,
        httponly=True,
        secure=False,  # localhost development only; HTTPS requires True.
        samesite="lax",
        path="/auth",
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/auth/callback")
def cognito_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    state_cookie: str | None = Cookie(default=None, alias=STATE_COOKIE),
):
    if error:
        raise HTTPException(status_code=400, detail="Cognito sign-in was not completed")
    if not code or not state or not state_cookie or not hmac.compare_digest(state, state_cookie):
        raise HTTPException(status_code=400, detail="Invalid sign-in callback state")

    with _lock:
        pending = _pending.pop(state, None)

    if pending is None or pending[1] < time.monotonic():
        raise HTTPException(status_code=400, detail="Sign-in attempt expired; try again")

    verifier = pending[0]
    token_payload = {
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "code_verifier": verifier,
    }
    token_request = Request(
        f"{COGNITO_DOMAIN}/oauth2/token",
        data=urlencode(token_payload).encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urlopen(token_request, timeout=25) as aws_response:
            token_data = json.load(aws_response)
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        print("Cognito token exchange failed:", type(exc).__name__)
        raise HTTPException(status_code=502, detail="Cognito token exchange failed") from None

    access_token = token_data.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise HTTPException(status_code=502, detail="No Cognito access token returned")

    # This function verifies JWT claims and ensures the Cognito account
    # actually maps to a synthetic patient in AWS RDS.
    try:
        patient_id = resolve_patient_from_access_token(access_token)
    except Exception as exc:
        print("Patient identity verification failed:", type(exc).__name__)
        raise HTTPException(status_code=401, detail="Account is not linked to a patient") from None

    session_id = secrets.token_urlsafe(48)
    with _lock:
        _sessions[session_id] = (access_token, time.monotonic() + 1800)
        _csrf_tokens[session_id] = secrets.token_urlsafe(32)

    response = RedirectResponse(STREAMLIT_URL, status_code=303)
    response.set_cookie(
        key=SESSION_COOKIE,
        value=session_id,
        max_age=1800,
        httponly=True,
        secure=False,  # localhost development only.
        samesite="lax",
        path="/",
    )
    response.delete_cookie(STATE_COOKIE, path="/auth")
    response.headers["Cache-Control"] = "no-store"
    print("Demo login succeeded for linked patient; no token printed")
    return response


@app.get("/auth/me")
def current_patient(session_id: str | None = Cookie(default=None, alias=SESSION_COOKIE)):
    if not session_id:
        raise HTTPException(status_code=401, detail="Not signed in")

    with _lock:
        record = _sessions.get(session_id)

    if not record or record[1] < time.monotonic():
        raise HTTPException(status_code=401, detail="Session expired")

    access_token = record[0]
    try:
        patient_id = resolve_patient_from_access_token(access_token)
    except Exception:
        with _lock:
            _sessions.pop(session_id, None)
            _csrf_tokens.pop(session_id, None)
        raise HTTPException(status_code=401, detail="Session expired") from None

    return {"authenticated": True, "patient_id": patient_id}


@app.get("/auth/appointments")
def my_appointments(
    session_id: str | None = Cookie(default=None, alias=SESSION_COOKIE),
):
    """Read-only, session-protected list of this patient's appointments.

    The browser/Streamlit never sends a patient ID or a Cognito token.
    The backend maps the stored access token to its patient in AWS RDS.
    """
    if not session_id:
        raise HTTPException(status_code=401, detail="Sign in required")

    with _lock:
        session = _sessions.get(session_id)

    if session is None or session[1] <= time.monotonic():
        raise HTTPException(status_code=401, detail="Session expired")

    try:
        # Existing service re-verifies the Cognito access token
        # and derives the patient ID before querying AWS RDS.
        result = get_my_appointments(session[0])
    except Exception as exc:
        # Do not send access tokens, patient data or backend errors to UI.
        print("Appointment lookup failed:", type(exc).__name__)
        raise HTTPException(
            status_code=503,
            detail="Appointments are temporarily unavailable",
        ) from None

    # Return only fields needed by the dashboard.
    allowed_fields = (
        "appointment_id", "doctor_name", "specialty",
        "date", "time", "status",
    )
    appointments = []
    for record in result["appointments"]:
        appointments.append({
            key: record[key]
            for key in allowed_fields
            if key in record
        })

    appointments.sort(
        key=lambda item: (
            str(item.get("date", "")),
            str(item.get("time", "")),
        )
    )
    payload = {
        "count": len(appointments),
        "appointments": jsonable_encoder(appointments),
    }
    return JSONResponse(
        content=payload,
        headers={"Cache-Control": "no-store", "Vary": "Cookie"},
    )


@app.get("/auth/logout")
def logout(session_id: str | None = Cookie(default=None, alias=SESSION_COOKIE)):
    # Logout is a local-demo browser navigation. Use POST + CSRF controls
    # when implementing production-grade session termination.
    if session_id:
        with _lock:
            _sessions.pop(session_id, None)
            _csrf_tokens.pop(session_id, None)
    response = RedirectResponse(STREAMLIT_URL, status_code=303)
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.headers["Cache-Control"] = "no-store"
    return response


# -------------------------------------------------------
# Step 11.7.4: trusted, authenticated patient actions
# -------------------------------------------------------
# Deliberately NOT part of the AI agent's MCP tool allowlist.
# Only local Streamlit buttons call these endpoints.
# The bearer access token stays in this backend process.
# A session-bound CSRF token protects every state-changing request.

class BookingIntentBody(BaseModel):
    slot_id: str = Field(min_length=1, max_length=20)


class CancellationIntentBody(BaseModel):
    appointment_id: str = Field(min_length=1, max_length=50)


class RescheduleIntentBody(BaseModel):
    appointment_id: str = Field(min_length=1, max_length=50)
    new_slot_id: str = Field(min_length=1, max_length=20)


def _active_access_token(session_id: str | None) -> str:
    if not session_id:
        raise HTTPException(status_code=401, detail="Sign in required")
    with _lock:
        saved = _sessions.get(session_id)
    if saved is None or saved[1] <= time.monotonic():
        raise HTTPException(status_code=401, detail="Session expired. Sign in again")

    # Validate on every action. Never accept a patient ID from Streamlit.
    access_token = saved[0]
    try:
        resolve_patient_from_access_token(access_token)
    except Exception:
        with _lock:
            _sessions.pop(session_id, None)
            _csrf_tokens.pop(session_id, None)
        raise HTTPException(status_code=401, detail="Session expired. Sign in again") from None
    return access_token


def _authorized_write(session_id: str | None, csrf_header: str | None) -> str:
    access_token = _active_access_token(session_id)
    with _lock:
        expected_csrf = _csrf_tokens.get(session_id)

    if (
        not expected_csrf
        or not csrf_header
        or not hmac.compare_digest(expected_csrf, csrf_header)
    ):
        raise HTTPException(status_code=403, detail="Request verification failed")
    return access_token


def _safe_action(operation, *args):
    """Use existing transactional services; never print private data."""
    try:
        value = operation(*args)
        return JSONResponse(
            content=jsonable_encoder(value),
            headers={"Cache-Control": "no-store", "Vary": "Cookie"},
        )
    except ValueError as exc:
        # Expired intents, unavailable slots and ownership checks.
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except Exception as exc:
        print("Clinic appointment action failed:", type(exc).__name__)
        raise HTTPException(
            status_code=503,
            detail="Appointment service temporarily unavailable",
        ) from None


@app.get("/auth/csrf")
def csrf_for_session(
    session_id: str | None = Cookie(default=None, alias=SESSION_COOKIE),
):
    _active_access_token(session_id)
    with _lock:
        csrf = _csrf_tokens.get(session_id)
    if csrf is None:
        raise HTTPException(status_code=401, detail="Sign in again")
    return JSONResponse(
        content={"csrf_token": csrf},
        headers={"Cache-Control": "no-store", "Vary": "Cookie"},
    )


@app.get("/auth/available-slots")
def available_slots_for_patient(
    session_id: str | None = Cookie(default=None, alias=SESSION_COOKIE),
):
    _active_access_token(session_id)
    try:
        with get_cloud_connection() as conn:
            slots = conn.execute("""
                SELECT s.slot_id, s.date, s.time,
                       d.name AS doctor_name, d.specialty
                FROM slots s
                JOIN doctors d ON d.doctor_id = s.doctor_id
                WHERE s.status = 'available'
                  AND (s.date + s.time) >
                      (CURRENT_TIMESTAMP AT TIME ZONE 'Europe/London')
                ORDER BY s.date, s.time, s.slot_id
                LIMIT 80
            """).fetchall()
    except Exception as exc:
        print("Available slots lookup failed:", type(exc).__name__)
        raise HTTPException(status_code=503, detail="Available slots unavailable") from None

    records = [
        {
            "slot_id": record["slot_id"],
            "doctor_name": record["doctor_name"],
            "specialty": record["specialty"],
            "date": record["date"].isoformat(),
            "time": record["time"].strftime("%H:%M"),
        }
        for record in slots
    ]
    return JSONResponse(
        content={"slots": records, "count": len(records)},
        headers={"Cache-Control": "no-store", "Vary": "Cookie"},
    )


@app.post("/auth/booking-intents")
def prepare_booking_ui(
    body: BookingIntentBody,
    session_id: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    csrf: str | None = Header(default=None, alias="X-CSRF-Token"),
):
    token = _authorized_write(session_id, csrf)
    return _safe_action(create_booking_intent, token, body.slot_id)


@app.post("/auth/booking-intents/{intent_id}/confirm")
def confirm_booking_ui(
    intent_id: str,
    session_id: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    csrf: str | None = Header(default=None, alias="X-CSRF-Token"),
):
    token = _authorized_write(session_id, csrf)
    # Confirm is invoked ONLY when the authenticated patient clicks
    # the approval button in the trusted Streamlit interface.
    return _safe_action(confirm_booking_intent, token, intent_id, "CONFIRM")


@app.post("/auth/cancellation-intents")
def prepare_cancellation_ui(
    body: CancellationIntentBody,
    session_id: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    csrf: str | None = Header(default=None, alias="X-CSRF-Token"),
):
    token = _authorized_write(session_id, csrf)
    return _safe_action(create_cancellation_intent, token, body.appointment_id)


@app.post("/auth/cancellation-intents/{intent_id}/confirm")
def confirm_cancellation_ui(
    intent_id: str,
    session_id: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    csrf: str | None = Header(default=None, alias="X-CSRF-Token"),
):
    token = _authorized_write(session_id, csrf)
    return _safe_action(confirm_cancellation, token, intent_id, "CONFIRM CANCEL")


@app.post("/auth/reschedule-intents")
def prepare_rescheduling_ui(
    body: RescheduleIntentBody,
    session_id: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    csrf: str | None = Header(default=None, alias="X-CSRF-Token"),
):
    token = _authorized_write(session_id, csrf)
    return _safe_action(
        create_reschedule_intent,
        token,
        body.appointment_id,
        body.new_slot_id,
    )


@app.post("/auth/reschedule-intents/{intent_id}/confirm")
def confirm_rescheduling_ui(
    intent_id: str,
    session_id: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    csrf: str | None = Header(default=None, alias="X-CSRF-Token"),
):
    token = _authorized_write(session_id, csrf)
    return _safe_action(confirm_reschedule, token, intent_id, "CONFIRM RESCHEDULE")
