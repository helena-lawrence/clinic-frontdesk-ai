
from app.auth.cognito_auth import (
    get_auth_config,
    verify_cognito_access_token,
    AuthenticationError
)


def main():

    print("=== AWS COGNITO AUTH TEST ===")

    # 1. Check configuration
    issuer, client_id, jwks_url = get_auth_config()

    print("Cognito configuration loaded")
    print("Issuer:", issuer)
    print("App client configured:", bool(client_id))

    assert issuer.startswith(
        "https://cognito-idp.eu-west-2.amazonaws.com/"
    )

    print("PASS: Cognito configuration")

    # 2. Reject an empty access token
    try:
        verify_cognito_access_token("")

        raise AssertionError(
            "Empty token was incorrectly accepted"
        )

    except AuthenticationError:
        print("PASS: Empty access token rejected")

    # 3. Reject a malformed JWT
    try:
        verify_cognito_access_token("invalid.jwt.token")

        raise AssertionError(
            "Invalid JWT was incorrectly accepted"
        )

    except AuthenticationError:
        print("PASS: Invalid JWT rejected")

    print("\nCOGNITO AUTH NEGATIVE TESTS PASSED")


if __name__ == "__main__":
    main()
