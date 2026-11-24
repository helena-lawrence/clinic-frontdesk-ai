
import re


EMERGENCY_MESSAGE = (
    "If this is a medical emergency, call 999 now. "
    "This assistant cannot provide emergency care."
)

MEDICAL_MESSAGE = (
    "I can help with clinic appointments and policies, "
    "but I cannot diagnose medical conditions or "
    "recommend treatments. Please contact a qualified "
    "healthcare professional. For urgent, non-emergency "
    "medical help in England, contact NHS 111."
)

INJECTION_MESSAGE = (
    "I cannot follow instructions that attempt to "
    "override the clinic assistant's safety rules."
)


# Illustrative patterns for our synthetic demo.
EMERGENCY_PATTERNS = [
    r"\bchest pain\b",
    r"\bheart attack\b",
    r"\bstroke\b",
    r"\b(?:cannot|can't|cant|unable to|struggling to)\s+breathe\b",
    r"\b(?:difficulty breathing|severe breathing difficulty)\b",
    r"\b(?:not breathing|gasping for air)\b",
    r"\bsevere bleeding\b",
    r"\b(?:kill myself|end my life|suicidal)\b"
]

MEDICAL_PATTERNS = [
    r"\bdiagnose me\b",
    r"\bdo i have\b",
    r"\bwhat illness\b",
    r"\b(?:what|which) (?:medicine|medication|treatment)\b",
    r"\bwhat dose\b",
    r"\bhow much medication\b",
    r"\bwhat should i take for\b"
]

INJECTION_PATTERNS = [
    r"\bignore (?:all |your |the )?(?:previous |prior )?instructions\b",
    r"\b(?:reveal|show) (?:me )?(?:your |the )?system prompt\b",
    r"\bbypass (?:your |the )?safety rules\b",
    r"\byou are now (?:an|a) unrestricted\b"
]


def matches_any(text, patterns):
    return any(
        re.search(pattern, text, flags=re.IGNORECASE)
        for pattern in patterns
    )


def check_input_safety(message):
    """
    Run deterministic checks before RAG or LLM calls.

    Returns:
        None if no rule matched.
        A dictionary with a fixed response otherwise.
    """

    if not isinstance(message, str) or not message.strip():
        raise ValueError("Message cannot be empty")

    message = message.strip()

    if len(message) > 1000:
        raise ValueError("Message exceeds maximum length")

    # Emergency checks take highest priority.
    if matches_any(message, EMERGENCY_PATTERNS):
        return {
            "route": "emergency",
            "answer": EMERGENCY_MESSAGE
        }

    if matches_any(message, MEDICAL_PATTERNS):
        return {
            "route": "medical_refusal",
            "answer": MEDICAL_MESSAGE
        }

    if matches_any(message, INJECTION_PATTERNS):
        return {
            "route": "prompt_injection",
            "answer": INJECTION_MESSAGE
        }

    return None
