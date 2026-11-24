
import json

from pathlib import Path
from dotenv import load_dotenv
from pydantic import AnyHttpUrl

from mcp.server import MCPServer
from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.auth.middleware.auth_context import (
    get_access_token
)

from app.auth.cognito_auth import (
    get_auth_config,
    verify_cognito_access_token
)

from app.booking.authenticated_booking import (
    get_my_appointments
)


# Load existing AWS configuration
BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")

RESOURCE_URL = "http://127.0.0.1:8001/mcp"

issuer, client_id, _ = get_auth_config()


# Verify Cognito access tokens on incoming HTTP requests
class CognitoTokenVerifier(TokenVerifier):

    async def verify_token(
        self,
        token: str
    ) -> AccessToken | None:

        try:
            identity = verify_cognito_access_token(token)

            if identity.get("authenticated") is not True:
                return None

            if identity.get("client_id") != client_id:
                return None

            if not identity.get("cognito_sub"):
                return None

            return AccessToken(
                token=token,
                client_id=client_id,
                scopes=[],
                subject=identity["cognito_sub"]
            )

        except Exception:
            # Reject invalid tokens without logging secrets
            return None


# Protected MCP server
mcp = MCPServer(
    "Clinic Patient MCP",
    token_verifier=CognitoTokenVerifier(),
    auth=AuthSettings(
        issuer_url=AnyHttpUrl(issuer),
        resource_server_url=AnyHttpUrl(RESOURCE_URL),
        required_scopes=[],
        validate_token_resource=False
    )
)


@mcp.tool()
def list_my_clinic_appointments() -> dict:
    """
    List appointments for the authenticated patient.

    The tool accepts no patient ID or access token
    as model-generated arguments.
    """

    verified_token = get_access_token()

    if verified_token is None:
        raise PermissionError(
            "Authenticated HTTP request required"
        )

    # This existing service independently validates
    # Cognito and resolves the patient from AWS RDS.
    result = get_my_appointments(
        verified_token.token
    )

    # Convert dates/times into JSON-compatible values.
    return json.loads(
        json.dumps(result, default=str)
    )


if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host="127.0.0.1",
        port=8001
    )
