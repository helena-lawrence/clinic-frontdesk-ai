
import json
from functools import lru_cache
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer


BASE_DIR = Path(__file__).resolve().parents[2]

EMBEDDINGS_FILE = (
    BASE_DIR / "data" / "processed" / "clinic_embeddings.json"
)


@lru_cache(maxsize=1)
def load_embeddings():
    """Load and validate stored clinic embeddings."""

    if not EMBEDDINGS_FILE.exists():
        raise FileNotFoundError(
            "Embeddings not found. Run generate_embeddings.py first."
        )

    with open(EMBEDDINGS_FILE, encoding="utf-8") as file:
        data = json.load(file)

    records = data["records"]

    if not records:
        raise ValueError("No clinic embeddings found")

    vectors = np.asarray(
        [record["vector"] for record in records],
        dtype=np.float32
    )

    if (
        vectors.ndim != 2
        or vectors.shape[1] != data["vector_dimension"]
        or len(records) != data["total_chunks"]
    ):
        raise ValueError("Invalid embedding dimensions or count")

    if not np.isfinite(vectors).all():
        raise ValueError("Invalid embedding values")

    norms = np.linalg.norm(vectors, axis=1)

    if np.any(norms == 0):
        raise ValueError("Zero-length embedding found")

    vectors = vectors / norms[:, None]

    return records, vectors, data["embedding_model"]


@lru_cache(maxsize=1)
def get_embedding_model(model_name):
    return SentenceTransformer(model_name, device="cpu")


def search_clinic_knowledge(query, top_k=3):
    """Find clinic chunks most similar to a patient question."""

    if not isinstance(query, str) or not query.strip():
        raise ValueError("Query cannot be empty")

    if type(top_k) is not int or top_k < 1:
        raise ValueError("top_k must be a positive integer")

    # 1. Load stored document vectors
    records, vectors, model_name = load_embeddings()

    # 2. Convert patient question to an embedding
    model = get_embedding_model(model_name)

    query_vector = np.asarray(
        model.encode(
            query.strip(),
            normalize_embeddings=True,
            convert_to_numpy=True
        ),
        dtype=np.float32
    )

    if query_vector.shape != (vectors.shape[1],):
        raise ValueError("Query embedding dimension mismatch")

    # 3. Calculate cosine similarity
    similarity_scores = vectors @ query_vector

    # 4. Select highest-scoring chunks
    top_indices = np.argsort(
        -similarity_scores,
        kind="stable"
    )[:top_k]

    # 5. Return matching content and source metadata
    results = []

    for index in top_indices:
        chunk = records[int(index)]

        results.append({
            "chunk_id": chunk["chunk_id"],
            "document_id": chunk["document_id"],
            "title": chunk["title"],
            "content": chunk["content"],
            "score": round(float(similarity_scores[index]), 4)
        })

    return results
