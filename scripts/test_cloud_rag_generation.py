
from app.rag.cloud_generator import (
    generate_rag_answer,
    FALLBACK_MESSAGE
)


questions = [
    "Can I cancel my appointment?",
    "What time does the clinic open?",
    "Can I reschedule my appointment?"
]


print("=== AWS CLOUD RAG GENERATION TEST ===")


for question in questions:

    print("\n" + "=" * 60)
    print("QUESTION:", question)

    result = generate_rag_answer(
        question=question,
        top_k=3
    )

    print("\nGENERATED ANSWER:")
    print(result["answer"])

    print("\nCITED SOURCES:")

    for source in result["sources"]:
        print(
            f"- {source['document_id']} "
            f"({source['title']})"
        )

    print("\nLLM:", result["llm_model"])

    assert result["answer"]
    assert result["answer"] != FALLBACK_MESSAGE
    assert result["sources"]


print("\nAWS CLOUD RAG GENERATION TEST PASSED")
