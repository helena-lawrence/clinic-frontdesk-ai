
import asyncio

from mcp import Client

from app.mcp_server.server import mcp
from scripts.test_mcp_server import extract_tool_data


async def main():

    print("=== MCP CLOUD ML TOOL TEST ===")

    async with Client(mcp) as client:

        # 1. Verify tool registration
        tools_result = await client.list_tools()

        tool_names = [
            tool.name
            for tool in tools_result.tools
        ]

        assert "predict_demo_no_show_risk" in tool_names

        print("PASS: MCP ML tool registered")

        # 2. Test two fictional scenarios
        scenarios = [
            "good_attendance",
            "prior_no_shows"
        ]

        for scenario in scenarios:

            print("\n" + "=" * 50)
            print("Scenario:", scenario)

            # Invoke the ML tool through MCP
            response = await client.call_tool(
                "predict_demo_no_show_risk",
                {"scenario": scenario}
            )

            result = extract_tool_data(response)

            print("\nAWS ML prediction:")
            print(result)

            # 3. Validate cloud prediction
            assert result["scenario"] == scenario

            assert result["model_name"]

            assert (
                0 <= result["no_show_score"] <= 1
            )

            assert isinstance(
                result["predicted_no_show"],
                bool
            )

            assert result["data_source"] == "synthetic"

            print("PASS: AWS ML prediction through MCP")

    print("\nMCP CLOUD ML TOOL TEST PASSED")


if __name__ == "__main__":
    asyncio.run(main())
