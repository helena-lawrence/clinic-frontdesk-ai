
from app.auth.cognito_auth import (
    verify_cognito_access_token,
    get_auth_config,
    AuthenticationError
)

from app.core.cloud_db import get_cloud_connection


def resolve_patient_from_access_token(access_token: str) -> str:
    """
    Verify the Cognito access token and resolve
    the authenticated patient's ID from AWS RDS.

    Never accept patient_id from the caller.
    """

    # 1. Verify the Cognito JWT
    identity = verify_cognito_access_token(
        access_token
    )

    cognito_sub = identity["cognito_sub"]

    # 2. Get the trusted Cognito User Pool ID
    issuer, _, _ = get_auth_config()

    pool_id = issuer.rsplit("/", 1)[-1]

    # 3. Find the linked patient in AWS RDS
    with get_cloud_connection() as conn:

        result = conn.execute(
            """
            SELECT p.patient_id
            FROM patient_identities pi
            JOIN patients p
                ON pi.patient_id = p.patient_id
            WHERE pi.cognito_user_pool_id = %s
              AND pi.cognito_sub = %s
            """,
            (pool_id, cognito_sub)
        ).fetchone()

    # 4. Reject unlinked accounts
    if result is None:
        raise AuthenticationError(
            "Authenticated account is not linked "
            "to a clinic patient record"
        )

    return result["patient_id"]
