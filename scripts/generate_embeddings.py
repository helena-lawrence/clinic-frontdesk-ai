
import json
import numpy as np

from pathlib import Path
from sentence_transformers import SentenceTransformer


BASE_DIR = Path(__file__).resolve().parent.parent

INPUT_FILE = (
    BASE_DIR / "data" / "processed" / "clinic_chunks.json"
)

OUTPUT_FILE = (
    BASE_DIR / "data" / "processed" / "clinic_embeddings.json"
)

MODEL_NAME = "BAAI/bge-small-en-v1.5"
EXPECTED_DIMENSION = 384


def generate_embeddings():

    print("=== CLINIC RAG EMBEDDING GENERATION ===")

    # Step 1: Load the chunks
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            "Chunk file not found. Complete Step 10.3 first."
        )

    with open(INPUT_FILE, "r", encoding="utf-8") as file:
        chunks = json.load(file)

    if not chunks:
        raise ValueError("No chunks found")

    chunk_ids = [chunk["chunk_id"] for chunk in chunks]

    if len(chunk_ids) != len(set(chunk_ids)):
        raise ValueError("Duplicate chunk IDs detected")

    print(f"Loaded chunks: {len(chunks)}")

    # Step 2: Load embedding model
    print(f"\nLoading model: {MODEL_NAME}")

    model = SentenceTransformer(
        MODEL_NAME,
        device="cpu"
    )

    # Step 3: Prepare text for embedding
    texts = [
        f"{chunk['title']}\n{chunk['content']}"
        for chunk in chunks
    ]

    # Step 4: Generate normalized vectors
    print("\nGenerating embeddings...")

    vectors = model.encode(
        texts,
        batch_size=16,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True
    )

    # Step 5: Validate embeddings
    if len(vectors) != len(chunks):
        raise ValueError("Embedding count mismatch")

    dimension = int(vectors.shape[1])

    if dimension != EXPECTED_DIMENSION:
        raise ValueError(
            f"Unexpected embedding dimension: {dimension}"
        )

    if not np.isfinite(vectors).all():
        raise ValueError("Invalid embedding values detected")

    print(f"Generated vectors: {len(vectors)}")
    print(f"Vector dimension: {dimension}")

    # Step 6: Combine embeddings with metadata
    records = []

    for chunk, vector in zip(chunks, vectors):

        record = {
            "chunk_id": chunk["chunk_id"],
            "document_id": chunk["document_id"],
            "title": chunk["title"],
            "category": chunk["category"],
            "source": chunk["source"],
            "is_synthetic": chunk["is_synthetic"],
            "content": chunk["content"],
            "vector": vector.tolist()
        }

        records.append(record)

    # Step 7: Save embeddings
    output = {
        "embedding_model": MODEL_NAME,
        "vector_dimension": dimension,
        "total_chunks": len(records),
        "records": records
    }

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(output, file, indent=2)

    print("\nEmbeddings saved successfully!")
    print(f"Output: {OUTPUT_FILE}")

    # Step 8: Print sample
    sample = records[0]

    print("\nSample embedding:")
    print(f"Chunk ID: {sample['chunk_id']}")
    print(f"Document: {sample['title']}")
    print(f"Dimension: {len(sample['vector'])}")
    print(f"First 5 values: {sample['vector'][:5]}")

    print("\nEMBEDDING GENERATION COMPLETED")


if __name__ == "__main__":
    generate_embeddings()
