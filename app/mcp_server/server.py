from typing import Literal
from app.mcp_server.appointment_tools import (
    register_appointment_tools
)
from app.ml.cloud_inference import predict_no_show_cloud
from mcp.server import MCPServer

from app.core.cloud_db import get_cloud_connection
from app.booking.booking_service import get_available_slots
from app.rag.safe_assistant import safe_clinic_answer
from app.guardrails.output_checks import (
    PII_PATTERNS,
    contains_pattern
)


mcp = MCPServer(
    "clinic-frontdesk-tools",
    version="0.1.0"
)
register_appointment_tools(mcp)

@mcp.tool()
def list_clinic_doctors() -> dict:
    """
    List doctors and their specialties.

    Read-only tool using AWS RDS PostgreSQL.
    Does not return patient information.
    """

    with get_cloud_connection() as conn:
        rows = conn.execute(
            """
            SELECT doctor_id, name, specialty
            FROM doctors
            ORDER BY doctor_id
            LIMIT 20
            """
        ).fetchall()

    doctors = [
        {
            "doctor_id": row["doctor_id"],
            "name": row["name"],
            "specialty": row["specialty"]
        }
        for row in rows
    ]

    return {
        "count": len(doctors),
        "doctors": doctors
    }


@mcp.tool()
def get_available_clinic_slots(
    doctor_id: str | None = None,
    limit: int = 10
) -> dict:
    """
    Retrieve future available appointment slots.

    Read-only tool using the AWS cloud booking service.
    Does not create or modify appointments.
    """

    if not 1 <= limit <= 20:
        raise ValueError("Limit must be between 1 and 20")

    if doctor_id is not None:
        if not doctor_id or len(doctor_id) > 20:
            raise ValueError("Invalid doctor ID")

    slots = get_available_slots(
        doctor_id=doctor_id
    )

    selected = slots[:limit]

    return {
        "count": len(selected),
        "slots": selected
    }

@mcp.tool()
def predict_demo_no_show_risk(
    scenario: Literal["good_attendance", "prior_no_shows"]
) -> dict:
    """
    Run AWS Lambda no-show prediction using
    predefined synthetic appointment features.

    No patient records are accessed.
    No appointments are modified.
    ML inference runs only in AWS Lambda.
    """

    # Synthetic demonstration scenarios
    scenarios = {
        "good_attendance": {
            "lead_time_days": 2,
            "day_of_week": 0,
            "appointment_hour": 10,
            "reminder_planned": 1,
            "previous_appointments": 5,
            "previous_no_shows": 0
        },
        "prior_no_shows": {
            "lead_time_days": 21,
            "day_of_week": 4,
            "appointment_hour": 9,
            "reminder_planned": 0,
            "previous_appointments": 5,
            "previous_no_shows": 3
        }
    }

    if scenario not in scenarios:
        raise ValueError(
            "Invalid scenario. Choose "
            "'good_attendance' or 'prior_no_shows'."
        )

    features = scenarios[scenario]

    # Invoke trained ML model in AWS Lambda
    prediction = predict_no_show_cloud(features)

    return {
        "scenario": scenario,
        "features": features,
        "model_name": prediction["model_name"],
        "no_show_score": prediction["no_show_score"],
        "predicted_no_show": prediction["predicted_no_show"],
        "threshold": prediction["threshold"],
        "data_source": prediction["data_source"],
        "warning": (
            "Synthetic demonstration score only. "
            "Not validated for clinical decisions or "
            "appointment denial."
        )
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")

@mcp.tool()
def answer_clinic_policy(question: str) -> dict:
    """
    Answer general clinic policy and FAQ questions.

    Uses AWS Bedrock and PostgreSQL pgvector.
    Applies input and output guardrails.

    Does not access patient records or modify bookings.
    """

    if not isinstance(question, str) or not question.strip():
        raise ValueError("Question cannot be empty")

    if len(question) > 1000:
        raise ValueError("Question is too long")

    # Do not send obvious personal identifiers to Bedrock.
    if contains_pattern(question, PII_PATTERNS):
        return {
            "answer": (
                "Please ask your clinic policy question "
                "without including personal information."
            ),
            "sources": [],
            "route": "privacy_refusal"
        }

    # Existing input guardrails, AWS RAG and output checks
    result = safe_clinic_answer(question)

    # Return only fields needed by the MCP client
    return {
        "answer": result["answer"],
        "sources": result.get("sources", []),
        "route": result["route"]
    }
