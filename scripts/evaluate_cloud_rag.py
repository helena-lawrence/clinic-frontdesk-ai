
import json
from datetime import datetime, timezone
from pathlib import Path

from app.rag.cloud_retriever import (
    search_clinic_knowledge_cloud
)


BASE_DIR = Path(__file__).resolve().parent.parent

REPORT_PATH = (
    BASE_DIR / "data" / "processed" / "rag_evaluation.json"
)


TEST_CASES = [
    {
        "question": "Can I cancel my appointment with less than 24 hours notice?",
        "expected_document": "POL-003"
    },
    {
        "question": "What time does the clinic open on Monday?",
        "expected_document": "POL-001"
    },
    {
        "question": "Can I move my appointment to another date?",
        "expected_document": "POL-004"
    },
    {
        "question": "Will the clinic automatically send me a reminder?",
        "expected_document": "POL-005"
    },
    {
        "question": "Can I access another patient's appointment information?",
        "expected_document": "POL-006"
    },
    {
        "question": "How do I book an appointment with a doctor?",
        "expected_document": "POL-002"
    },
    {
        "question": "What happens to my old appointment slot when I reschedule?",
        "expected_document": "POL-004"
    },
    {
        "question": "Can the assistant diagnose my medical condition?",
        "expected_document": "FAQ-001"
    }
]


def evaluate_retrieval():

    print("=== AWS RAG RETRIEVAL EVALUATION ===")

    results = []

    hit_at_1 = 0
    hit_at_3 = 0
    reciprocal_rank_total = 0

    for index, test in enumerate(TEST_CASES, start=1):

        question = test["question"]
        expected = test["expected_document"]

        print(f"\nTest {index}: {question}")

        # Retrieve from AWS Bedrock + RDS pgvector
        retrieved = search_clinic_knowledge_cloud(
            query=question,
            top_k=3
        )

        retrieved_ids = [
            item["document_id"]
            for item in retrieved
        ]

        # Identify the first occurrence of the expected document
        rank = next(
            (
                position
                for position, document_id
                in enumerate(retrieved_ids, start=1)
                if document_id == expected
            ),
            None
        )

        hit1 = rank == 1
        hit3 = rank is not None
        reciprocal_rank = 1 / rank if rank else 0

        hit_at_1 += int(hit1)
        hit_at_3 += int(hit3)
        reciprocal_rank_total += reciprocal_rank

        results.append({
            "question": question,
            "expected_document": expected,
            "retrieved_documents": retrieved_ids,
            "expected_rank": rank,
            "hit_at_1": hit1,
            "hit_at_3": hit3
        })

        print("Expected:", expected)
        print("Retrieved:", retrieved_ids)
        print("Rank:", rank if rank else "Not found")
        print("Hit@3:", "PASS" if hit3 else "FAIL")

    total = len(TEST_CASES)

    metrics = {
        "hit_at_1": round(hit_at_1 / total, 4),
        "hit_at_3": round(hit_at_3 / total, 4),
        "mrr_at_3": round(
            reciprocal_rank_total / total, 4
        )
    }

    print("\n=== FINAL EVALUATION RESULTS ===")

    print(f"Total questions: {total}")
    print(f"Hit@1: {metrics['hit_at_1']:.2%}")
    print(f"Hit@3: {metrics['hit_at_3']:.2%}")
    print(f"MRR@3: {metrics['mrr_at_3']:.4f}")

    report = {
        "evaluated_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "metrics": metrics,
        "test_cases": results
    }

    REPORT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    REPORT_PATH.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8"
    )

    print(f"\nReport saved: {REPORT_PATH}")
    print("\nRAG RETRIEVAL EVALUATION COMPLETED")


if __name__ == "__main__":
    evaluate_retrieval()
