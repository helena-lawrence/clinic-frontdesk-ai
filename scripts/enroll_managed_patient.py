"""Link an invited Cognito user to one synthetic patient record."""

import os

from app.core.cloud_db import get_cloud_connection


def main():
    pool_id = os.environ["COGNITO_USER_POOL_ID"]
    cognito_sub = os.environ["COGNITO_SUB"]
    patient_id = os.environ["PATIENT_ID"]

    if not pool_id.startswith("eu-west-2_") or not cognito_sub or not patient_id:
        raise ValueError("Invalid enrollment inputs")

    with get_cloud_connection() as conn:
        patient = conn.execute(
            "SELECT patient_id FROM patients WHERE patient_id = %s", (patient_id,)
        ).fetchone()
        if patient is None:
            raise ValueError("Synthetic patient does not exist")

        conn.execute(
            """
            INSERT INTO patient_identities (cognito_user_pool_id, cognito_sub, patient_id)
            VALUES (%s, %s, %s)
            ON CONFLICT (cognito_user_pool_id, cognito_sub) DO NOTHING
            """,
            (pool_id, cognito_sub, patient_id),
        )

        linked = conn.execute(
            "SELECT patient_id FROM patient_identities WHERE cognito_user_pool_id = %s AND cognito_sub = %s",
            (pool_id, cognito_sub),
        ).fetchone()
        if linked is None or linked["patient_id"] != patient_id:
            raise ValueError("Cognito user is linked to another patient")

    print("Cognito user linked to synthetic patient")


if __name__ == "__main__":
    main()
