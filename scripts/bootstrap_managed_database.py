"""Initialize a new, empty managed clinic database with synthetic demo data."""

from app.core.cloud_db import get_cloud_connection
from scripts.create_cloud_tables import create_tables
from scripts.create_booking_intents_table import create_table as create_booking_intents
from scripts.create_cancellation_intents_table import create_table as create_cancellation_intents
from scripts.create_reschedule_intents_table import main as create_reschedule_intents
from scripts.seed_cloud_database import seed_cloud_database
from scripts.seed_cloud_attendance import seed_cloud_attendance


def main():
    from scripts.setup_cloud_database import setup_database

    setup_database()
    create_tables()
    create_booking_intents()
    create_cancellation_intents()
    create_reschedule_intents()

    with get_cloud_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS patient_identities (
                cognito_user_pool_id TEXT NOT NULL,
                cognito_sub TEXT NOT NULL,
                patient_id VARCHAR(20) NOT NULL UNIQUE REFERENCES patients(patient_id),
                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (cognito_user_pool_id, cognito_sub)
            )
        """)

    # All data is freshly generated inside this task; nothing is copied from RDS.
    import scripts.generate_synthetic_data  # noqa: F401

    seed_cloud_database()
    seed_cloud_attendance()

    from scripts.generate_clinic_documents import generate_documents

    from scripts.ingest_clinic_documents import ingest_documents
    from scripts.chunk_clinic_documents import chunk_documents
    from scripts.store_bedrock_embeddings import store_embeddings

    generate_documents()
    ingest_documents()
    chunk_documents()
    store_embeddings()


if __name__ == "__main__":
    main()
