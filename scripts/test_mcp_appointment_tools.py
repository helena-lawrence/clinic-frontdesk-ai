
import asyncio
import json

from mcp import Client

from app.mcp_server.server import mcp
from app.core.cloud_db import get_cloud_connection


async def main():

    print("=== MCP APPOINTMENT INTEGRATION TEST ===")

    # Find one future available synthetic slot.
    with get_cloud_connection() as conn:
        slot = conn.execute("""
            SELECT slot_id
            FROM slots
            WHERE status = 'available'
              AND date + time >
                  (NOW() AT TIME ZONE 'Europe/London')
            ORDER BY date, time
            LIMIT 1
        """).fetchone()

    if slot is None:
        raise RuntimeError(
            "No future available test slot found"
        )

    slot_id = slot["slot_id"]

    # Connect directly to our existing MCP server.
    async with Client(mcp) as client:

        tools = await client.list_tools()

        tool_names = [
            tool.name for tool in tools.tools
        ]

        print("Registered MCP tools:")
        for name in tool_names:
            print("-", name)

        assert (
            "preview_clinic_appointment"
            in tool_names
        )

        print("\nPASS: Appointment tool registered")

        # Call the real MCP tool.
        result = await client.call_tool(
            "preview_clinic_appointment",
            {"slot_id": slot_id}
        )

        if result.is_error:
            raise RuntimeError(
                "MCP appointment preview failed"
            )

        # MCP can return structured data or text.
        data = result.structured_content

        if data is None:
            text_blocks = [
                item.text
                for item in result.content
                if item.type == "text"
            ]

            if not text_blocks:
                raise RuntimeError(
                    "MCP returned no appointment data"
                )

            data = json.loads(text_blocks[0])

        print("\nMCP appointment preview:")
        print(json.dumps(data, indent=2))

        assert data["slot_id"] == slot_id
        assert data["available"] is True
        assert data["confirmation_required"] is True
        assert data["booking_created"] is False

        print("\nPASS: MCP appointment preview")
        print("PASS: No booking was created")

    print("\nMCP APPOINTMENT INTEGRATION TEST PASSED")


if __name__ == "__main__":
    asyncio.run(main())
