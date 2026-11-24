
import os
from functools import lru_cache
from pathlib import Path

import jwt
from jwt import PyJWKClient
from jwt.exceptions import InvalidTokenError, PyJWKClientError

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")


class AuthenticationError(Exception):
    """Raised when authentication fails."""
    pass


@lru_cache(maxsize=1)
def get_auth_config():
    """Load Cognito configuration."""

    region = os.getenv("COGNITO_REGION", "eu-west-2")
    pool_id = os.getenv("COGNITO_USER_POOL_ID", "")
    client_id = os.getenv("COGNITO_CLIENT_ID", "")

    if not pool_id.startswith(f"{region}_"):
        raise RuntimeError("Invalid Cognito User Pool ID")

    if not client_id or client_id.startswith("YOUR_"):
        raise RuntimeError("Missing Cognito App Client ID")

    issuer = (
        f"https://cognito-idp.{region}.amazonaws.com/"
        f"{pool_id}"
    )

    jwks_url = f"{issuer}/.well-known/jwks.json"

    return issuer, client_id, jwks_url


@lru_cache(maxsize=1)
def get_jwks_client():
    """Get Cognito's public signing keys."""

    _, _, jwks_url = get_auth_config()

    return PyJWKClient(
        jwks_url,
        timeout=5
    )


def verify_cognito_access_token(token: str) -> dict:
    """
    Validate an Amazon Cognito access token.

    Checks:
    - JWT signature
    - RS256 signing algorithm
    - Cognito issuer
    - Token expiry
    - Token type
    - App client ID

    Returns only verified identity information.
    """

    if not isinstance(token, str) or not token.strip():
        raise AuthenticationError("Access token is required")

    token = token.strip()

    if len(token) > 12000:
        raise AuthenticationError("Invalid access token")

    issuer, client_id, _ = get_auth_config()

    try:
        # 1. Inspect the JWT header
        header = jwt.get_unverified_header(token)

        if header.get("alg") != "RS256":
            raise AuthenticationError(
                "Unsupported JWT signing algorithm"
            )

        # 2. Find Cognito's matching public key
        signing_key = (
            get_jwks_client()
            .get_signing_key_from_jwt(token)
            .key
        )

        # 3. Verify signature and standard claims
        claims = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            issuer=issuer,
            options={
                "verify_aud": False,
                "require": [
                    "exp",
                    "iat",
                    "iss",
                    "sub",
                    "token_use",
                    "client_id"
                ]
            },
            leeway=30
        )

    except (InvalidTokenError, PyJWKClientError) as exc:
        raise AuthenticationError(
            "Invalid or expired Cognito access token"
        ) from exc

    # 4. Check token purpose
    if claims["token_use"] != "access":
        raise AuthenticationError(
            "Expected a Cognito access token"
        )

    # 5. Verify application client
    if claims["client_id"] != client_id:
        raise AuthenticationError(
            "Token belongs to a different application"
        )

    # 6. Verify user identifier
    cognito_sub = claims["sub"]

    if not isinstance(cognito_sub, str) or not cognito_sub:
        raise AuthenticationError(
            "Missing Cognito user identity"
        )

    # 7. Return verified identity only
    return {
        "cognito_sub": cognito_sub,
        "client_id": claims["client_id"],
        "scope": claims.get("scope", ""),
        "authenticated": True
    }
