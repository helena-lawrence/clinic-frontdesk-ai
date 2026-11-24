
import asyncio
from unittest.mock import patch

from mcp import Client

from app.mcp_server.server import mcp
from scripts.test_mcp_server import extract_tool_data


async def main():

    print("=== MCP RAG TOOL TEST ===")

    async with Client(mcp) as client:

        # 1. Verify tool registration
        tools = await client.list_tools()

        tool_names = [
            tool.name for tool in tools.tools
        ]

        assert "answer_clinic_policy" in tool_names

        print("PASS: RAG tool registered")

        # 2. Test response through MCP
        # Mock the RAG implementation for this test.
        with patch(
            "app.mcp_server.server.safe_clinic_answer",
            return_value={
                "answer": (
                    "Patients can cancel appointments. "
                    "[POL-003]"
                ),
                "sources": [
                    {
                        "document_id": "POL-003",
                        "chunk_id": "POL-003-C001",
                        "title": "Appointment Cancellation Policy"
                    }
                ],
                "route": "rag"
            }
        ):

            response = await client.call_tool(
                "answer_clinic_policy",
                {
                    "question": (
                        "Can I cancel my appointment?"
                    )
                }
            )

            result = extract_tool_data(response)

            assert result["route"] == "rag"
            assert result["sources"][0]["document_id"] == "POL-003"

            print("PASS: MCP RAG response")

        # 3. Verify obvious personal data is rejected
        with patch(
            "app.mcp_server.server.safe_clinic_answer"
        ) as mock_rag:

            response = await client.call_tool(
                "answer_clinic_policy",
                {
                    "question": (
                        "My email is test@example.com. "
                        "What are the opening hours?"
                    )
                }
            )

            result = extract_tool_data(response)

            assert result["route"] == "privacy_refusal"
            mock_rag.assert_not_called()

            print("PASS: Personal data blocked")

        # 4. Live AWS RAG integration
        print("\nCalling live AWS RAG...")

        response = await client.call_tool(
            "answer_clinic_policy",
            {
                "question": (
                    "What are the clinic opening hours?"
                )
            }
        )

        result = extract_tool_data(response)

        print("\nAnswer:")
        print(result["answer"])

        print("\nSources:")
        print(result["sources"])

        print("\nRoute:", result["route"])

        assert result["answer"]
        assert result["route"] == "rag"
        assert result["sources"]

    print("\nMCP RAG TOOL TEST PASSED")


if __name__ == "__main__":
    asyncio.run(main())
