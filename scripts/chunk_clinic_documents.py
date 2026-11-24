
import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

INPUT_FILE = BASE_DIR / "data" / "processed" / "clinic_documents.json"
OUTPUT_FILE = BASE_DIR / "data" / "processed" / "clinic_chunks.json"


def create_chunk(document, chunk_number, content, chunk_type):
    """Create one chunk with source metadata."""

    chunk_id = (
        f"{document['document_id']}-C{chunk_number:03d}"
    )

    return {
        "chunk_id": chunk_id,
        "document_id": document["document_id"],
        "title": document["title"],
        "category": document["category"],
        "source": document["source"],
        "source_file": document["source_file"],
        "is_synthetic": document["is_synthetic"],
        "chunk_type": chunk_type,
        "content": content,
        "word_count": len(content.split())
    }


def chunk_policy(document):
    """
    Keep the complete policy together.

    Our current policies are short and each
    document covers one topic.
    """

    content = document["content"].strip()

    if not content:
        raise ValueError("Policy content cannot be empty")

    if len(content.split()) > 250:
        raise ValueError(
            f"{document['document_id']} is too large "
            "for single-topic chunking. Review it manually."
        )

    return [
        create_chunk(
            document=document,
            chunk_number=1,
            content=content,
            chunk_type="policy"
        )
    ]


def chunk_faq(document):
    """
    Each FAQ question and answer becomes one chunk.
    Never separate a question from its answer.
    """

    chunks = []

    for index, paragraph in enumerate(
        document["paragraphs"], start=1
    ):

        match = re.fullmatch(
            r"Question:\s*(.+?)\s+Answer:\s*(.+)",
            paragraph.strip(),
            flags=re.IGNORECASE | re.DOTALL
        )

        if not match:
            raise ValueError(
                f"Invalid FAQ format in "
                f"{document['document_id']}, "
                f"paragraph {index}"
            )

        question = match.group(1).strip()
        answer = match.group(2).strip()

        if not question or not answer:
            raise ValueError("FAQ question or answer is empty")

        content = (
            f"Question: {question}\n"
            f"Answer: {answer}"
        )

        chunks.append(
            create_chunk(
                document=document,
                chunk_number=index,
                content=content,
                chunk_type="faq"
            )
        )

    return chunks


def chunk_documents():

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            "Processed documents not found. "
            "Run document ingestion first."
        )

    with open(INPUT_FILE, "r", encoding="utf-8") as file:
        documents = json.load(file)

    all_chunks = []

    for document in documents:

        if document["category"] == "faq":
            chunks = chunk_faq(document)
        else:
            chunks = chunk_policy(document)

        all_chunks.extend(chunks)

        print(
            f"{document['document_id']}: "
            f"{len(chunks)} chunks created"
        )

    # Validate chunk IDs and content
    chunk_ids = [c["chunk_id"] for c in all_chunks]

    if len(chunk_ids) != len(set(chunk_ids)):
        raise ValueError("Duplicate chunk IDs detected")

    if any(not c["content"].strip() for c in all_chunks):
        raise ValueError("Empty chunk detected")

    # Save the final chunks
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            all_chunks,
            file,
            indent=4,
            ensure_ascii=False
        )

    print("\nChunking completed successfully!")
    print(f"Total documents: {len(documents)}")
    print(f"Total chunks: {len(all_chunks)}")
    print(f"Saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    chunk_documents()
