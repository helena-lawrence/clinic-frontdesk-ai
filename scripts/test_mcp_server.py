
import asyncio
import json

from mcp import Client
from mcp.types import TextContent

from app.mcp_server.server import mcp


def extract_tool_data(result):
    """
    Extract data from an MCP tool response.

    Supports structured_content and JSON text content.
    """

    # Check for MCP tool execution errors
    if result.is_error:
        error_text = "\n".join(
            block.text
            for block in result.content
            if isinstance(block, TextContent)
        )

        raise RuntimeError(
            f"MCP tool failed: {error_text}"
        )

    # First, try structured output
    if result.structured_content is not None:
        return result.structured_content

    # Fallback: read text content
    text_blocks = [
        block.text
        for block in result.content
        if isinstance(block, TextContent)
    ]

    if not text_blocks:
        raise RuntimeError(
            "MCP returned no structured or text content"
        )

    text = "\n".join(text_blocks)

    try:
        return json.loads(text)

    except json.JSONDecodeError:
        print("MCP raw text response:", text)

        raise RuntimeError(
            "MCP returned text that is not valid JSON"
        )


async def main():

    print("=== CLINIC MCP SERVER TEST ===")

    async with Client(mcp) as client:

        # 1. Discover MCP tools
        tools_result = await client.list_tools()

        tool_names = [
            tool.name
            for tool in tools_result.tools
        ]

        print("\nRegistered MCP tools:")

        for name in tool_names:
            print("-", name)

        assert "list_clinic_doctors" in tool_names
        assert "get_available_clinic_slots" in tool_names

        # 2. Test doctor tool
        print("\nCalling doctor tool...")

        doctors_result = await client.call_tool(
            "list_clinic_doctors",
            {}
        )

        doctors_data = extract_tool_data(
            doctors_result
        )

        print("Doctors retrieved from AWS:")
        print(doctors_data)

        assert isinstance(doctors_data, dict)
        assert isinstance(doctors_data["doctors"], list)
        assert doctors_data["count"] >= 1

        print("PASS: Doctor MCP tool")

        # 3. Test available slots tool
        print("\nCalling appointment slots tool...")

        slots_result = await client.call_tool(
            "get_available_clinic_slots",
            {"limit": 5}
        )

        slots_data = extract_tool_data(
            slots_result
        )

        print("Available slots retrieved from AWS:")
        print(slots_data)

        assert isinstance(slots_data, dict)
        assert isinstance(slots_data["slots"], list)
        assert slots_data["count"] <= 5

        print("PASS: Appointment slots MCP tool")

    print("\nMCP SERVER TEST PASSED")


if __name__ == "__main__":
    asyncio.run(main())
