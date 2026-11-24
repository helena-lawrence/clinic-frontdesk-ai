
import json

import boto3
from botocore.config import Config


AWS_REGION = "eu-west-2"

MODEL_ID = "amazon.titan-embed-text-v2:0"

EMBEDDING_DIMENSION = 1024


def generate_embedding(text):
    """
    Generate text embeddings using Amazon Bedrock.

    The embedding model runs entirely in AWS.
    """

    if not isinstance(text, str) or not text.strip():
        raise ValueError("Input text cannot be empty")

    if len(text) > 50000:
        raise ValueError("Input text is too long")

    # 1. Create AWS Bedrock Runtime client
    client = boto3.client(
        "bedrock-runtime",
        region_name=AWS_REGION,
        config=Config(
            connect_timeout=10,
            read_timeout=60
        )
    )

    # 2. Prepare model request
    request_body = {
        "inputText": text.strip(),
        "dimensions": EMBEDDING_DIMENSION,
        "normalize": True
    }

    # 3. Invoke the cloud embedding model
    response = client.invoke_model(
        modelId=MODEL_ID,
        body=json.dumps(request_body),
        contentType="application/json",
        accept="application/json"
    )

    # 4. Read model response
    response_body = json.loads(
        response["body"].read()
    )

    embedding = response_body.get("embedding")

    # 5. Validate returned embedding
    if not isinstance(embedding, list):
        raise RuntimeError(
            "Bedrock did not return an embedding"
        )

    if len(embedding) != EMBEDDING_DIMENSION:
        raise RuntimeError(
            "Unexpected embedding dimension: "
            f"{len(embedding)}"
        )

    return embedding
