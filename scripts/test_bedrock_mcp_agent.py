
import asyncio

from app.agent.bedrock_mcp_agent import ask_agent


async def main():

    print("=== BEDROCK MCP AGENT TEST ===")

    question = (
        "Which doctors are registered at the clinic? "
        "Please use the clinic records."
    )

    print("\nPatient:", question)

    answer, called_tools = await ask_agent(
        question,
        force_doctor_lookup=True
    )

    print("\nAgent answer:")
    print(answer)

    print("\nMCP tools used:", called_tools)

    assert "list_clinic_doctors" in called_tools
    assert answer.strip()

    print("\nPASS: Bedrock invoked MCP")
    print("PASS: MCP doctor lookup executed")
    print("PASS: Bedrock produced an answer")

    print("\nBEDROCK MCP AGENT TEST PASSED")


if __name__ == "__main__":
    asyncio.run(main())
