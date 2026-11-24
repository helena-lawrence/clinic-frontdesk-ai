
import asyncio

from app.agent.bedrock_mcp_agent import ask_agent


async def main():

    print("=== BEDROCK RAG AND ML AGENT TEST ===")

    # --------------------------------------
    # Test 1: Clinic policy RAG
    # --------------------------------------

    print("\nTEST 1 — CLINIC RAG")

    question = (
        "What is the clinic policy for cancelling "
        "an appointment? Use the clinic documents."
    )

    answer, tools = await ask_agent(
        question,
        force_tool="answer_clinic_policy"
    )

    print("\nRAG answer:")
    print(answer)

    print("MCP tools called:", tools)

    assert "answer_clinic_policy" in tools
    assert answer.strip()

    print("\nPASS: Agent called clinic RAG tool")

    # --------------------------------------
    # Test 2: AWS Lambda synthetic ML
    # --------------------------------------

    print("\nTEST 2 — CLOUD ML")

    question = (
        "For a fictional synthetic demo only, "
        "run the clinic no-show prediction example. "
        "Explain the result as demonstration data, "
        "not a real patient prediction."
    )

    answer, tools = await ask_agent(
        question,
        force_tool="predict_demo_no_show_risk"
    )

    print("\nML answer:")
    print(answer)

    print("MCP tools called:", tools)

    assert "predict_demo_no_show_risk" in tools
    assert answer.strip()

    print("\nPASS: Agent called AWS Lambda ML tool")

    # --------------------------------------
    # Final result
    # --------------------------------------

    print("\nBEDROCK RAG AND ML AGENT TEST PASSED")


if __name__ == "__main__":
    asyncio.run(main())
