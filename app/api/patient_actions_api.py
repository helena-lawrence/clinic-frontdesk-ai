
from typing import Literal

from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import (
    HTTPBearer,
    HTTPAuthorizationCredentials
)
from pydantic import BaseModel, Field
from jwt import PyJWTError

from app.auth.cognito_auth import AuthenticationError
from app.auth.patient_identity import (
    resolve_patient_from_access_token
)
from app.booking.authenticated_booking import (
    get_my_appointments
)
from app.booking.confirmed_booking import (
    create_booking_intent,
    confirm_booking_intent
)
from app.booking.confirmed_cancellation import (
    create_cancellation_intent,
    confirm_cancellation
)
from app.booking.confirmed_reschedule import (
    create_reschedule_intent,
    confirm_reschedule
)


app = FastAPI(title="Clinic Patient Actions API")

bearer = HTTPBearer(auto_error=False)


# ------------------------------------------
# Request models
# ------------------------------------------

class BookingRequest(BaseModel):
    slot_id: str = Field(min_length=1, max_length=20)


class CancellationRequest(BaseModel):
    appointment_id: str = Field(min_length=1, max_length=50)


class RescheduleRequest(BaseModel):
    appointment_id: str = Field(min_length=1, max_length=50)
    new_slot_id: str = Field(min_length=1, max_length=20)


class BookingConfirmation(BaseModel):
    confirmation: Literal["CONFIRM"]


class CancellationConfirmation(BaseModel):
    confirmation: Literal["CONFIRM CANCEL"]


class RescheduleConfirmation(BaseModel):
    confirmation: Literal["CONFIRM RESCHEDULE"]


# ------------------------------------------
# Authentication
# ------------------------------------------

def require_patient_token(
    credentials: HTTPAuthorizationCredentials | None
        = Depends(bearer)
) -> str:

    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Authentication required"
        )

    token = credentials.credentials

    try:
        # Verify JWT and AWS patient mapping.
        resolve_patient_from_access_token(token)

    except (
        AuthenticationError,
        PyJWTError,
        ValueError,
        KeyError,
        TypeError
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid or unlinked patient token"
        )

    return token


# ------------------------------------------
# Error handling for booking rules
# ------------------------------------------

def run_booking_action(function, *args):

    try:
        return function(*args)

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc)
        )


# ------------------------------------------
# Health check
# ------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok"}


# ------------------------------------------
# Read own appointments
# ------------------------------------------

@app.get("/patient/appointments")
def my_appointments(
    token: str = Depends(require_patient_token)
):
    return get_my_appointments(token)


# ------------------------------------------
# Booking
# ------------------------------------------

@app.post("/patient/booking-intents")
def prepare_booking(
    request: BookingRequest,
    token: str = Depends(require_patient_token)
):
    return run_booking_action(
        create_booking_intent,
        token,
        request.slot_id
    )


@app.post("/patient/booking-intents/{intent_id}/confirm")
def approve_booking(
    intent_id: str,
    request: BookingConfirmation,
    token: str = Depends(require_patient_token)
):
    return run_booking_action(
        confirm_booking_intent,
        token,
        intent_id,
        request.confirmation
    )


# ------------------------------------------
# Cancellation
# ------------------------------------------

@app.post("/patient/cancellation-intents")
def prepare_cancellation(
    request: CancellationRequest,
    token: str = Depends(require_patient_token)
):
    return run_booking_action(
        create_cancellation_intent,
        token,
        request.appointment_id
    )


@app.post("/patient/cancellation-intents/{intent_id}/confirm")
def approve_cancellation(
    intent_id: str,
    request: CancellationConfirmation,
    token: str = Depends(require_patient_token)
):
    return run_booking_action(
        confirm_cancellation,
        token,
        intent_id,
        request.confirmation
    )


# ------------------------------------------
# Rescheduling
# ------------------------------------------

@app.post("/patient/reschedule-intents")
def prepare_reschedule(
    request: RescheduleRequest,
    token: str = Depends(require_patient_token)
):
    return run_booking_action(
        create_reschedule_intent,
        token,
        request.appointment_id,
        request.new_slot_id
    )


@app.post("/patient/reschedule-intents/{intent_id}/confirm")
def approve_reschedule(
    intent_id: str,
    request: RescheduleConfirmation,
    token: str = Depends(require_patient_token)
):
    return run_booking_action(
        confirm_reschedule,
        token,
        intent_id,
        request.confirmation
    )
