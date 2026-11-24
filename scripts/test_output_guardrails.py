
import io
import logging

from unittest.mock import patch

from app.rag.safe_assistant import safe_clinic_answer
from app.rag.cloud_generator import FALLBACK_MESSAGE


print("=== OUTPUT GUARDRAIL TEST ===")

source = {
    "document_id": "POL-003",
    "chunk_id": "POL-003-C001",
    "title": "Appointment Cancellation Policy"
}


def mock_result(answer):
    return {
        "answer": answer,
        "sources": [source],
        "llm_model": "amazon.nova-lite-v1:0"
    }


question = "Can I cancel my appointment?"

# Test 1: Valid grounded answer
with patch(
    "app.rag.safe_assistant.generate_rag_answer",
    return_value=mock_result(
        "Yes, you can cancel your appointment. [POL-003]"
    )
):
    result = safe_clinic_answer(question)

    assert result["route"] == "rag"
    assert len(result["sources"]) == 1

print("PASS: Valid cited answer")


# Test 2: Reject invented document citation
with patch(
    "app.rag.safe_assistant.generate_rag_answer",
    return_value=mock_result(
        "Cancellation is allowed. [POL-999]"
    )
):
    result = safe_clinic_answer(question)

    assert result["route"] == "output_blocked"
    assert result["answer"] == FALLBACK_MESSAGE
    assert result["sources"] == []

print("PASS: Unsupported citation blocked")


# Test 3: Reject answer exposing an email
with patch(
    "app.rag.safe_assistant.generate_rag_answer",
    return_value=mock_result(
        "Contact private.person@example.com. [POL-003]"
    )
):
    result = safe_clinic_answer(question)

    assert result["route"] == "output_blocked"
    assert "private.person@example.com" not in result["answer"]

print("PASS: Personal information blocked")


# Test 4: Reject medical dosage instructions
with patch(
    "app.rag.safe_assistant.generate_rag_answer",
    return_value=mock_result(
        "You should take 500mg of medication. [POL-003]"
    )
):
    result = safe_clinic_answer(question)

    assert result["route"] == "medical_refusal"
    assert result["sources"] == []

print("PASS: Medical instructions blocked")


# Test 5: Ensure emergency bypasses AWS RAG
with patch(
    "app.rag.safe_assistant.generate_rag_answer"
) as mock_rag:

    result = safe_clinic_answer(
        "I am having chest pain"
    )

    assert result["route"] == "emergency"
    mock_rag.assert_not_called()

print("PASS: Emergency bypasses RAG")


# Test 6: Verify privacy-safe logging
log_output = io.StringIO()

handler = logging.StreamHandler(log_output)
logger = logging.getLogger("clinic.frontdesk")

original_level = logger.level

logger.addHandler(handler)
logger.setLevel(logging.INFO)

try:
    with patch(
        "app.rag.safe_assistant.generate_rag_answer",
        return_value=mock_result(
            "Email private.person@example.com. [POL-003]"
        )
    ):
        safe_clinic_answer(question)

    log_text = log_output.getvalue()

    assert "request_id=" in log_text
    assert "route=output_blocked" in log_text

    assert question not in log_text
    assert "private.person@example.com" not in log_text

finally:
    logger.removeHandler(handler)
    logger.setLevel(original_level)
    handler.close()

print("PASS: Application logging excludes question and answer")

print("\nOUTPUT GUARDRAIL TEST PASSED")
