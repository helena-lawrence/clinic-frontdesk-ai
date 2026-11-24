
from app.core.cloud_db import get_cloud_connection


def create_table():
    print("=== BOOKING CONFIRMATION TABLE SETUP ===")

    with get_cloud_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS booking_intents (
                intent_id UUID PRIMARY KEY,
                patient_id VARCHAR(20) NOT NULL
                    REFERENCES patients(patient_id),
                slot_id VARCHAR(20) NOT NULL
                    REFERENCES slots(slot_id),
                status VARCHAR(20) NOT NULL
                    DEFAULT 'pending'
                    CHECK (status IN ('pending', 'confirmed')),
                appointment_id VARCHAR(50)
                    REFERENCES appointments(appointment_id),
                expires_at TIMESTAMPTZ NOT NULL,
                created_at TIMESTAMPTZ NOT NULL
                    DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS
                idx_booking_intents_patient
            ON booking_intents(patient_id, status)
        """)

    print("BOOKING CONFIRMATION TABLE CREATED")


if __name__ == "__main__":
    create_table()
