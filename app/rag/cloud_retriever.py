
import json
import math

from app.core.cloud_db import get_cloud_connection

from app.rag.bedrock_embeddings import (
    generate_embedding,
    MODEL_ID,
    EMBEDDING_DIMENSION
)


def search_clinic_knowledge_cloud(query, top_k=3):
    """
    Retrieve relevant clinic policies using:

    1. Amazon Bedrock embeddings
    2. AWS RDS PostgreSQL
    3. pgvector cosine similarity

    No local embedding model or vector database.
    """

    # Step 1: Validate the question
    if not isinstance(query, str) or not query.strip():
        raise ValueError("Question cannot be empty")

    if len(query) > 1000:
        raise ValueError("Question is too long")

    if type(top_k) is not int or not 1 <= top_k <= 10:
        raise ValueError("top_k must be between 1 and 10")

    print("Generating query embedding using Amazon Bedrock...")

    # Step 2: Generate embedding in AWS
    query_embedding = generate_embedding(query.strip())

    if len(query_embedding) != EMBEDDING_DIMENSION:
        raise RuntimeError("Unexpected embedding dimension")

    if not all(math.isfinite(value) for value in query_embedding):
        raise RuntimeError("Invalid embedding values")

    # Convert to pgvector input format
    vector_value = json.dumps(query_embedding)

    print("Searching AWS PostgreSQL pgvector...")

    # Step 3: Search the cloud vector database
    with get_cloud_connection() as conn:

        database = conn.execute(
            "SELECT current_database() AS name"
        ).fetchone()["name"]

        if database != "clinicdb":
            raise RuntimeError("Connected to incorrect database")

        rows = conn.execute(
            """
            WITH query_vector AS (
                SELECT %s::vector AS embedding
            )
            SELECT
                c.chunk_id,
                c.document_id,
                c.title,
                c.category,
                c.source,
                c.content,
                c.embedding <=> q.embedding AS cosine_distance
            FROM clinic_knowledge_chunks c
            CROSS JOIN query_vector q
            WHERE c.embedding_model = %s
              AND c.is_synthetic = TRUE
            ORDER BY
                c.embedding <=> q.embedding ASC,
                c.chunk_id ASC
            LIMIT %s
            """,
            (
                vector_value,
                MODEL_ID,
                top_k
            )
        ).fetchall()

    if not rows:
        raise RuntimeError(
            "No matching cloud embeddings found. "
            "Check the pgvector table and embedding model."
        )

    # Step 4: Prepare retrieval results
    results = []

    for row in rows:

        cosine_distance = float(row["cosine_distance"])
        similarity = 1.0 - cosine_distance

        results.append({
            "chunk_id": row["chunk_id"],
            "document_id": row["document_id"],
            "title": row["title"],
            "category": row["category"],
            "source": row["source"],
            "content": row["content"],
            "similarity_score": round(similarity, 4)
        })

    return results
