
from app.rag.retriever import search_clinic_knowledge


questions = [
    "Can I cancel my appointment?",
    "What time does the clinic open?",
    "Can I change my appointment date?"
]


for question in questions:

    print("\n" + "=" * 50)
    print("QUESTION:", question)

    results = search_clinic_knowledge(
        query=question,
        top_k=3
    )

    assert len(results) == 3

    assert all(
        results[i]["score"] >= results[i + 1]["score"]
        for i in range(len(results) - 1)
    )

    for result in results:
        print("\nDocument:", result["document_id"])
        print("Title:", result["title"])
        print("Similarity:", result["score"])
        print("Content:", result["content"])

print("\nSEMANTIC RETRIEVAL TEST PASSED")
