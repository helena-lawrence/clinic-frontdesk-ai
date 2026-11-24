
import os
from pathlib import Path

from dotenv import load_dotenv

from app.core.cloud_db import get_cloud_connection


BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

PATIENT_ID = "P001"


def link_cognito_patient():

    print("=== COGNITO PATIENT IDENTITY SETUP ===")

    pool_id = os.getenv(
        "COGNITO_USER_POOL_ID", ""
    ).strip()

    if not pool_id.startswith("eu-west-2_"):
        raise ValueError(
            "Configure the correct Cognito User Pool ID "
            "in your .env file"
        )

    # Copy this from Cognito's User ID (sub) field.
    cognito_sub = input(
        "Enter Cognito User ID (sub): "
    ).strip()

    if not cognito_sub or len(cognito_sub) > 255:
        raise ValueError("Invalid Cognito user identifier")

    with get_cloud_connection() as conn:

        database = conn.execute(
            "SELECT current_database() AS name"
        ).fetchone()["name"]

        if database != "clinicdb":
            raise RuntimeError(
                f"Unexpected database: {database}"
            )

        # 1. Create the identity mapping table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS patient_identities (
                cognito_user_pool_id TEXT NOT NULL,
                cognito_sub TEXT NOT NULL,
                patient_id VARCHAR(20) NOT NULL UNIQUE
                    REFERENCES patients(patient_id),
                created_at TIMESTAMPTZ NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (
                    cognito_user_pool_id,
                    cognito_sub
                )
            )
        """)

        print("Identity mapping table ready")

        # 2. Verify the synthetic patient exists
        patient = conn.execute(
            """
            SELECT patient_id
            FROM patients
            WHERE patient_id = %s
            """,
            (PATIENT_ID,)
        ).fetchone()

        if not patient:
            raise ValueError(
                f"Patient {PATIENT_ID} not found"
            )

        # 3. Check for conflicting identity mappings
        existing_identity = conn.execute(
            """
            SELECT patient_id
            FROM patient_identities
            WHERE cognito_user_pool_id = %s
              AND cognito_sub = %s
            """,
            (pool_id, cognito_sub)
        ).fetchone()

        if existing_identity:
            if existing_identity["patient_id"] != PATIENT_ID:
                raise ValueError(
                    "Cognito identity is linked to "
                    "a different patient"
                )

            print("Identity mapping already exists")

        else:
            existing_patient = conn.execute(
                """
                SELECT cognito_sub
                FROM patient_identities
                WHERE patient_id = %s
                """,
                (PATIENT_ID,)
            ).fetchone()

            if existing_patient:
                raise ValueError(
                    "Patient is already linked to "
                    "a different Cognito identity"
                )

            # 4. Insert the verified demo mapping
            conn.execute(
                """
                INSERT INTO patient_identities (
                    cognito_user_pool_id,
                    cognito_sub,
                    patient_id
                )
                VALUES (%s, %s, %s)
                """,
                (
                    pool_id,
                    cognito_sub,
                    PATIENT_ID
                )
            )

            print("Cognito identity linked")

        # 5. Verify the mapping
        result = conn.execute(
            """
            SELECT patient_id
            FROM patient_identities
            WHERE cognito_user_pool_id = %s
              AND cognito_sub = %s
            """,
            (pool_id, cognito_sub)
        ).fetchone()

        assert result is not None
        assert result["patient_id"] == PATIENT_ID

        print("Mapped patient:", result["patient_id"])

    print("\nCOGNITO PATIENT MAPPING TEST PASSED")


if __name__ == "__main__":
    link_cognito_patient()
