
import asyncio
import json

import httpx2

from mcp import Client
from mcp.client.streamable_http import (
    streamable_http_client
)

from scripts.test_cognito_real_login import (
    test_real_login
)


MCP_URL = "http://127.0.0.1:8001/mcp"


async def check_anonymous_access():

    print("\nTesting unauthenticated access...")

    async with httpx2.AsyncClient(timeout=10) as http:
        response = await http.get(MCP_URL)

    assert response.status_code == 401, (
        f"Expected HTTP 401, got {response.status_code}"
    )

    print("PASS: Unauthenticated access rejected")


async def check_authenticated_access(access_token):

    print("\nConnecting to authenticated MCP server...")

    timeout = httpx2.Timeout(
        300.0,
        connect=30.0
    )

    async with httpx2.AsyncClient(
        headers={
            "Authorization": f"Bearer {access_token}"
        },
        timeout=timeout
    ) as http:

        transport = streamable_http_client(
            MCP_URL,
            http_client=http
        )

        async with Client(transport) as client:

            tools = await client.list_tools()

            tool_names = [
                tool.name for tool in tools.tools
            ]

            print("Available tools:", tool_names)

            assert "list_my_clinic_appointments" in tool_names

            result = await client.call_tool(
                "list_my_clinic_appointments",
                {}
            )

            if result.is_error:
                raise RuntimeError(
                    "Authenticated MCP appointment lookup failed"
                )

            data = result.structured_content

            if data is None:
                text_blocks = [
                    block.text
                    for block in result.content
                    if block.type == "text"
                ]

                if not text_blocks:
                    raise RuntimeError("Empty MCP response")

                data = json.loads(text_blocks[0])

            if (
                isinstance(data, dict)
                and "result" in data
                and isinstance(data["result"], dict)
            ):
                data = data["result"]

            assert isinstance(data, dict)
            assert isinstance(data["appointments"], list)
            assert data["count"] == len(data["appointments"])

            print(
                "Authenticated appointment count:",
                data["count"]
            )
            print("PASS: Patient appointments retrieved")
            print("PASS: No patient ID supplied to MCP")


def main():

    print("=== AUTHENTICATED MCP TEST ===")

    # Perform the existing Cognito login flow.
    # The token stays in application memory.
    access_token = test_real_login()

    if not access_token:
        raise RuntimeError(
            "Login test did not return an access token"
        )

    async def run_checks():
        await check_anonymous_access()
        await check_authenticated_access(access_token)

    asyncio.run(run_checks())

    print("\nAUTHENTICATED MCP TEST PASSED")


if __name__ == "__main__":
    main()
