
import json
import math
from pathlib import Path

from app.core.cloud_db import get_cloud_connection
from app.rag.bedrock_embeddings import (
    generate_embedding,
    MODEL_ID,
    EMBEDDING_DIMENSION
)


BASE_DIR = Path(__file__).resolve().parent.parent

CHUNKS_FILE = (
    BASE_DIR / "data" / "processed" / "clinic_chunks.json"
)

TABLE_NAME = "clinic_knowledge_chunks"


def store_embeddings():

    print("=== AWS BEDROCK + PGVECTOR SETUP ===")

    # 1. Load existing clinic chunks
    if not CHUNKS_FILE.exists():
        raise FileNotFoundError(
            "clinic_chunks.json not found"
        )

    with open(CHUNKS_FILE, "r", encoding="utf-8") as file:
        chunks = json.load(file)

    if not isinstance(chunks, list) or len(chunks) != 11:
        raise ValueError("Expected 11 clinic chunks")

    chunk_ids = [chunk["chunk_id"] for chunk in chunks]

    if len(set(chunk_ids)) != len(chunk_ids):
        raise ValueError("Duplicate chunk IDs detected")

    print(f"Loaded clinic chunks: {len(chunks)}")

    # 2. Connect to AWS PostgreSQL
    with get_cloud_connection() as conn:

        database = conn.execute(
            "SELECT current_database() AS name"
        ).fetchone()["name"]

        if database != "clinicdb":
            raise RuntimeError(
                f"Wrong database: {database}"
            )

        print(f"Connected to AWS database: {database}")

        # 3. Confirm pgvector is enabled
        extension = conn.execute(
            """
            SELECT extversion
            FROM pg_extension
            WHERE extname = 'vector'
            """
        ).fetchone()

        if not extension:
            raise RuntimeError(
                "pgvector extension is not enabled"
            )

        print("pgvector version:", extension["extversion"])

        # 4. Create the cloud vector table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS clinic_knowledge_chunks (
                chunk_id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                title TEXT NOT NULL,
                category TEXT NOT NULL,
                source TEXT NOT NULL,
                content TEXT NOT NULL,
                is_synthetic BOOLEAN NOT NULL,
                embedding_model TEXT NOT NULL,
                embedding VECTOR(1024) NOT NULL,
                updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()

        print("Cloud vector table ready")

        # 5. Generate and store embeddings
        for index, chunk in enumerate(chunks, start=1):

            chunk_id = chunk["chunk_id"]

            if chunk.get("is_synthetic") is not True:
                raise ValueError(
                    f"Expected synthetic document: {chunk_id}"
                )

            # Skip unchanged chunks on reruns
            existing = conn.execute(
                """
                SELECT title, content, embedding_model
                FROM clinic_knowledge_chunks
                WHERE chunk_id = %s
                """,
                (chunk_id,)
            ).fetchone()

            conn.commit()

            if existing and (
                existing["title"] == chunk["title"]
                and existing["content"] == chunk["content"]
                and existing["embedding_model"] == MODEL_ID
            ):
                print(f"[{index}/11] Already stored: {chunk_id}")
                continue

            text = (
                f"{chunk['title']}\n"
                f"{chunk['content']}"
            )

            print(f"[{index}/11] Embedding: {chunk_id}")

            # The model executes in Amazon Bedrock
            vector = generate_embedding(text)

            if len(vector) != EMBEDDING_DIMENSION:
                raise ValueError(
                    f"Incorrect vector size for {chunk_id}"
                )

            if not all(math.isfinite(v) for v in vector):
                raise ValueError("Invalid embedding values")

            # Serialize to pgvector's accepted vector format
            vector_value = json.dumps(vector)

            # Store directly in AWS PostgreSQL
            conn.execute(
                """
                INSERT INTO clinic_knowledge_chunks (
                    chunk_id,
                    document_id,
                    title,
                    category,
                    source,
                    content,
                    is_synthetic,
                    embedding_model,
                    embedding
                )
                VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s::vector
                )
                ON CONFLICT (chunk_id)
                DO UPDATE SET
                    document_id = EXCLUDED.document_id,
                    title = EXCLUDED.title,
                    category = EXCLUDED.category,
                    source = EXCLUDED.source,
                    content = EXCLUDED.content,
                    is_synthetic = EXCLUDED.is_synthetic,
                    embedding_model = EXCLUDED.embedding_model,
                    embedding = EXCLUDED.embedding,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    chunk["chunk_id"],
                    chunk["document_id"],
                    chunk["title"],
                    chunk["category"],
                    chunk["source"],
                    chunk["content"],
                    chunk["is_synthetic"],
                    MODEL_ID,
                    vector_value
                )
            )

            conn.commit()

            print(f"Stored in AWS: {chunk_id}")

        # 6. Verify cloud storage
        result = conn.execute(
            """
            SELECT
                COUNT(*) AS total,
                MIN(vector_dims(embedding)) AS min_dimension,
                MAX(vector_dims(embedding)) AS max_dimension
            FROM clinic_knowledge_chunks
            WHERE embedding_model = %s
            """,
            (MODEL_ID,)
        ).fetchone()

        print("\n=== AWS VECTOR VERIFICATION ===")
        print("Stored embeddings:", result["total"])
        print("Minimum dimension:", result["min_dimension"])
        print("Maximum dimension:", result["max_dimension"])

        if result["total"] != 11:
            raise RuntimeError(
                "Expected 11 cloud embeddings"
            )

        if (
            result["min_dimension"] != EMBEDDING_DIMENSION
            or result["max_dimension"] != EMBEDDING_DIMENSION
        ):
            raise RuntimeError("Vector dimension mismatch")

    print("\nAWS PGVECTOR STORAGE TEST PASSED")


if __name__ == "__main__":
    store_embeddings()
