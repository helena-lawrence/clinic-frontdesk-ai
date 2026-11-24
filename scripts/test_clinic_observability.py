"""Safe local test. No Bedrock, AWS Lambda or database calls."""
import asyncio
from app.core.observability import record_event, trace_agent

@trace_agent
async def demo():
    record_event(
        "bedrock", "converse", "success",
        duration_ms=12.4, model="demo-test-model",
        input_tokens=5, output_tokens=8,
    )
    record_event(
        "mcp", "answer_clinic_policy", "success",
        dependency="rag_pipeline", duration_ms=18.9,
    )
    record_event(
        "mcp", "predict_demo_no_show_risk", "success",
        dependency="aws_lambda_ml", duration_ms=26.1,
    )

if __name__ == "__main__":
    print("=== OBSERVABILITY SMOKE TEST (synthetic timings) ===")
    asyncio.run(demo())
    print("OBSERVABILITY SMOKE TEST PASSED")
