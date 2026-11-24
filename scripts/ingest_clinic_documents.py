
import json
import re

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SOURCE_DIR = (
    BASE_DIR / "data" / "synthetic" / "clinic_knowledge"
)

OUTPUT_DIR = BASE_DIR / "data" / "processed"
OUTPUT_FILE = OUTPUT_DIR / "clinic_documents.json"

REQUIRED_FIELDS = [
    "document_id",
    "title",
    "category",
    "source",
    "content"
]


def clean_document_text(text):
    """
    Remove unnecessary whitespace while
    preserving paragraph boundaries.
    """

    paragraphs = re.split(r"\n\s*\n", text.strip())

    cleaned_paragraphs = [
        " ".join(paragraph.split())
        for paragraph in paragraphs
        if paragraph.strip()
    ]

    return cleaned_paragraphs


def validate_document(document, filename):
    """
    Validate required document fields.
    """

    if not isinstance(document, dict):
        raise ValueError(
            f"{filename}: Document must be a JSON object"
        )

    for field in REQUIRED_FIELDS:

        value = document.get(field)

        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"{filename}: Missing or invalid field '{field}'"
            )

    if document.get("is_synthetic") is not True:
        raise ValueError(
            f"{filename}: Expected synthetic document"
        )

    if document["document_id"] != Path(filename).stem:
        raise ValueError(
            f"{filename}: Document ID does not match filename"
        )


def ingest_documents():

    if not SOURCE_DIR.exists():
        raise FileNotFoundError(
            "Clinic knowledge folder not found"
        )

    json_files = sorted(SOURCE_DIR.glob("*.json"))

    if not json_files:
        raise ValueError(
            "No clinic JSON documents found"
        )

    processed_documents = []
    seen_ids = set()

    for file_path in json_files:

        print(f"Processing: {file_path.name}")

        with open(
            file_path,
            "r",
            encoding="utf-8"
        ) as file:
            document = json.load(file)

        # 1. Validate document
        validate_document(document, file_path.name)

        document_id = document["document_id"]

        # 2. Prevent duplicate document IDs
        if document_id in seen_ids:
            raise ValueError(
                f"Duplicate document ID: {document_id}"
            )

        seen_ids.add(document_id)

        # 3. Clean and preserve paragraphs
        paragraphs = clean_document_text(
            document["content"]
        )

        if not paragraphs:
            raise ValueError(
                f"{document_id}: Empty document content"
            )

        cleaned_content = "\n\n".join(paragraphs)

        # 4. Prepare structured document
        processed_document = {
            "document_id": document_id,
            "title": document["title"].strip(),
            "category": document["category"].strip(),
            "source": document["source"].strip(),
            "source_file": file_path.name,
            "is_synthetic": True,
            "content": cleaned_content,
            "paragraphs": paragraphs,
            "word_count": len(cleaned_content.split())
        }

        processed_documents.append(processed_document)

        print(
            f"Validated: {document_id} | "
            f"Words: {processed_document['word_count']}"
        )

    # 5. Save validated documents
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            processed_documents,
            file,
            indent=4,
            ensure_ascii=False
        )

    print("\nDocument ingestion completed!")
    print(f"Total documents: {len(processed_documents)}")
    print(f"Output: {OUTPUT_FILE}")


if __name__ == "__main__":
    ingest_documents()
