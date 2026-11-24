
from app.rag.bedrock_embeddings import (
    generate_embedding,
    EMBEDDING_DIMENSION
)


print("=== AWS BEDROCK EMBEDDING TEST ===")

question = "Can I cancel my clinic appointment?"

print("Question:", question)
print("\nCalling Amazon Bedrock...")

embedding = generate_embedding(question)

print("\nEmbedding generated successfully!")
print("Embedding dimension:", len(embedding))
print("First five values:", embedding[:5])

assert len(embedding) == EMBEDDING_DIMENSION

print("\nAWS BEDROCK EMBEDDING TEST PASSED")
