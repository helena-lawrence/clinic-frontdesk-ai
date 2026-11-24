
import logging
import uuid

from app.guardrails.safety import check_input_safety
from app.guardrails.output_checks import validate_rag_output

from app.rag.cloud_generator import generate_rag_answer


logger = logging.getLogger("clinic.frontdesk")


def safe_clinic_answer(question):
    """
    Apply safety checks before and after
    AWS Bedrock RAG generation.

    Never log patient messages or generated answers.
    """

    request_id = uuid.uuid4().hex

    # 1. Input safety validation
    safety_result = check_input_safety(question)

    if safety_result is not None:

        logger.info(
            "request_id=%s route=%s",
            request_id,
            safety_result["route"]
        )

        return {
            "request_id": request_id,
            "question": question,
            "answer": safety_result["answer"],
            "sources": [],
            "route": safety_result["route"]
        }

    # 2. Invoke cloud RAG
    rag_result = generate_rag_answer(
        question=question,
        top_k=3
    )

    # 3. Validate LLM output
    checked_result = validate_rag_output(
        rag_result
    )

    # 4. Privacy-safe application logging
    logger.info(
        "request_id=%s route=%s source_count=%d",
        request_id,
        checked_result["route"],
        len(checked_result["sources"])
    )

    return {
        "request_id": request_id,
        "question": question,
        **checked_result
    }
