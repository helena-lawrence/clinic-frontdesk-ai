
import re

from app.rag.cloud_generator import FALLBACK_MESSAGE
from app.guardrails.safety import MEDICAL_MESSAGE


# Simple PII patterns for the demonstration
PII_PATTERNS = [
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
    r"(?<!\w)(?:\+44\s?7|07)(?:[\s-]?\d){9}\b",
    r"\bNHS\s*(?:number|no\.?)\s*[:#-]?\s*\d[\d\s-]{8,}\b"
]

# Examples of prohibited medical instructions
MEDICAL_OUTPUT_PATTERNS = [
    r"\byou should take\s+\d+\s*(?:mg|ml)\b",
    r"\btake\s+\d+\s*(?:mg|ml)\b",
    r"\byour diagnosis is\b",
    r"\bi diagnose you with\b"
]

CITATION_PATTERN = re.compile(
    r"\[([A-Z]{3}-\d{3})\]"
)


def contains_pattern(text, patterns):
    return any(
        re.search(pattern, text, re.IGNORECASE)
        for pattern in patterns
    )


def validate_rag_output(result):
    """
    Validate the LLM answer before returning it.

    Does not invoke any local or cloud ML model.
    """

    if not isinstance(result, dict):
        raise ValueError("Invalid RAG response")

    answer = result.get("answer", "")
    sources = result.get("sources", [])
    llm_model = result.get("llm_model")

    def blocked(message=FALLBACK_MESSAGE, route="output_blocked"):
        return {
            "answer": message,
            "sources": [],
            "llm_model": llm_model,
            "route": route
        }

    # 1. Reject empty or invalid answers
    if not isinstance(answer, str) or not answer.strip():
        return blocked()

    answer = answer.strip()

    if answer == FALLBACK_MESSAGE:
        return blocked(route="rag_fallback")

    if len(answer) > 2000:
        return blocked()

    # 2. Prevent obvious personal-data exposure
    if contains_pattern(answer, PII_PATTERNS):
        return blocked()

    # 3. Block obvious medical instructions
    if contains_pattern(answer, MEDICAL_OUTPUT_PATTERNS):
        return blocked(
            message=MEDICAL_MESSAGE,
            route="medical_refusal"
        )

    # 4. Verify citation references
    if not isinstance(sources, list):
        return blocked()

    if any(not isinstance(source, dict) for source in sources):
        return blocked()

    cited_ids = set(CITATION_PATTERN.findall(answer))

    source_ids = {
        source.get("document_id")
        for source in sources
    }

    if not cited_ids:
        return blocked()

    if not cited_ids.issubset(source_ids):
        return blocked()

    # 5. Return only the citations used in the answer
    verified_sources = [
        {
            "document_id": source["document_id"],
            "chunk_id": source.get("chunk_id"),
            "title": source.get("title")
        }
        for source in sources
        if source.get("document_id") in cited_ids
    ]

    return {
        "answer": answer,
        "sources": verified_sources,
        "llm_model": llm_model,
        "route": "rag"
    }
