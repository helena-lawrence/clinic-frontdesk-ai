
import json
import re

from datetime import datetime, timezone
from pathlib import Path

from app.core.cloud_db import get_cloud_connection

from app.rag.cloud_generator import (
    generate_rag_answer,
    FALLBACK_MESSAGE
)


BASE_DIR = Path(__file__).resolve().parent.parent

REPORT_FILE = (
    BASE_DIR / "data" / "processed"
    / "rag_answer_evaluation.json"
)


TEST_CASES = [
    {
        "question": "What are the clinic opening hours?",
        "expected_document": "POL-001",
        "expected_facts": (
            "Open Monday to Friday, 9 AM to 5 PM. "
            "Closed on weekends."
        )
    },
    {
        "question": "How can I book an appointment?",
        "expected_document": "POL-002",
        "expected_facts": (
            "Check slot availability, book an "
            "available slot and confirm only "
            "after the booking is saved."
        )
    },
    {
        "question": "Can I cancel with less than 24 hours notice?",
        "expected_document": "POL-003",
        "expected_facts": (
            "The clinic requests 24 hours notice "
            "where possible, but permits "
            "cancellation with less notice."
        )
    },
    {
        "question": "Can I change my appointment date?",
        "expected_document": "POL-004",
        "expected_facts": (
            "A new slot must be available. "
            "The old slot is released and "
            "a new reference is provided."
        )
    },
    {
        "question": "Will I automatically receive an SMS reminder?",
        "expected_document": "POL-005",
        "expected_facts": (
            "The demonstration system does not "
            "automatically send SMS or email reminders."
        )
    },
    {
        "question": "Can I view another patient's appointments?",
        "expected_document": "POL-006",
        "expected_facts": (
            "Patients must not access another "
            "patient's private appointment records."
        )
    }
]


def load_cited_evidence(sources):
    """Fetch cited source text from AWS PostgreSQL."""

    chunk_ids = [
        source["chunk_id"]
        for source in sources
    ]

    if not chunk_ids:
        return []

    with get_cloud_connection() as conn:
        rows = conn.execute(
            """
            SELECT chunk_id, document_id, content
            FROM clinic_knowledge_chunks
            WHERE chunk_id = ANY(%s)
            """,
            (chunk_ids,)
        ).fetchall()

    return [dict(row) for row in rows]


def evaluate_answers():

    print("=== CLOUD RAG ANSWER EVALUATION ===")

    results = []

    for index, test in enumerate(TEST_CASES, start=1):

        question = test["question"]

        print(f"\n{'=' * 60}")
        print(f"TEST {index}: {question}")

        # Bedrock embeddings + RDS retrieval + Bedrock LLM
        result = generate_rag_answer(
            question=question,
            top_k=3
        )

        answer = result["answer"]
        sources = result["sources"]

        cited_ids = set(
            re.findall(
                r"\[([A-Z]{3}-\d{3})\]",
                answer
            )
        )

        source_ids = {
            source["document_id"]
            for source in sources
        }

        citation_valid = (
            bool(cited_ids)
            and cited_ids.issubset(source_ids)
            and answer != FALLBACK_MESSAGE
        )

        expected_source_cited = (
            test["expected_document"] in cited_ids
        )

        evidence = load_cited_evidence(sources)

        print("\nGENERATED ANSWER:")
        print(answer)

        print("\nEXPECTED POLICY FACTS:")
        print(test["expected_facts"])

        print("\nCITED DOCUMENTS:")
        print(sorted(cited_ids))

        print("\nSUPPORTING SOURCE TEXT:")
        for source in evidence:
            print(f"\n{source['document_id']}:")
            print(source["content"])

        print("\nAUTOMATED CHECKS:")
        print("Citation valid:", citation_valid)
        print(
            "Expected source cited:",
            expected_source_cited
        )

        results.append({
            "question": question,
            "answer": answer,
            "expected_document": test["expected_document"],
            "expected_facts": test["expected_facts"],
            "cited_documents": sorted(cited_ids),
            "citation_valid": citation_valid,
            "expected_source_cited": expected_source_cited,
            "evidence": evidence,
            "manual_correctness": None,
            "manual_groundedness": None
        })

    total = len(results)

    citation_rate = sum(
        r["citation_valid"] for r in results
    ) / total

    expected_source_rate = sum(
        r["expected_source_cited"] for r in results
    ) / total

    report = {
        "evaluated_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "total_questions": total,
        "citation_valid_rate": round(citation_rate, 4),
        "expected_source_citation_rate": round(
            expected_source_rate, 4
        ),
        "manual_review_required": True,
        "results": results
    }

    REPORT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    REPORT_FILE.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print("\n=== EVALUATION SUMMARY ===")
    print(f"Total questions: {total}")
    print(f"Valid citations: {citation_rate:.2%}")
    print(
        "Expected source citation rate:",
        f"{expected_source_rate:.2%}"
    )
    print("Answer correctness: Requires manual review")
    print("Groundedness: Requires manual review")
    print(f"Report: {REPORT_FILE}")

    print("\nRAG ANSWER EVALUATION COMPLETED")


if __name__ == "__main__":
    evaluate_answers()
