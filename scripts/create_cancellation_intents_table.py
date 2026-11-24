
from app.core.cloud_db import get_cloud_connection


def create_table():

    print("=== CANCELLATION TABLE SETUP ===")

    with get_cloud_connection() as conn:

        conn.execute("""
            CREATE TABLE IF NOT EXISTS cancellation_intents (
                intent_id UUID PRIMARY KEY,

                patient_id VARCHAR(20) NOT NULL
                    REFERENCES patients(patient_id),

                appointment_id VARCHAR(50) NOT NULL
                    REFERENCES appointments(appointment_id),

                status VARCHAR(20) NOT NULL
                    DEFAULT 'pending'
                    CHECK (
                        status IN ('pending', 'confirmed')
                    ),

                expires_at TIMESTAMPTZ NOT NULL,

                created_at TIMESTAMPTZ NOT NULL
                    DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS
                idx_cancellation_intents_patient
            ON cancellation_intents (
                patient_id,
                status
            )
        """)

    print("CANCELLATION TABLE CREATED")


if __name__ == "__main__":
    create_table()
