
from app.rag.cloud_retriever import (
    search_clinic_knowledge_cloud
)


questions = [
    "Can I cancel my appointment?",
    "What time does the clinic open?",
    "Can I change my appointment date?"
]


print("=== AWS CLOUD RAG RETRIEVAL TEST ===")


for question in questions:

    print("\n" + "=" * 60)
    print("QUESTION:", question)

    results = search_clinic_knowledge_cloud(
        query=question,
        top_k=3
    )

    print("\nTOP 3 RETRIEVED DOCUMENTS:")

    for index, result in enumerate(results, start=1):

        print(f"\nResult {index}")
        print("Document:", result["document_id"])
        print("Chunk:", result["chunk_id"])
        print("Title:", result["title"])
        print("Similarity:", result["similarity_score"])
        print("Content:", result["content"])

    # Validate retrieval output
    assert len(results) == 3

    assert all(
        results[i]["similarity_score"]
        >= results[i + 1]["similarity_score"]
        for i in range(len(results) - 1)
    )

    assert all(
        result["document_id"]
        and result["chunk_id"]
        and result["content"]
        for result in results
    )


print("\nAWS CLOUD RAG RETRIEVAL TEST PASSED")
