
import json
import os

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, NoCredentialsError


AWS_REGION = "eu-west-2"
LAMBDA_FUNCTION = os.getenv("CLINIC_PREDICTOR_FUNCTION", "clinic-no-show-predictor")


def predict_no_show_cloud(features):
    """
    Send ML features to AWS Lambda.

    The ML model runs only in AWS.
    No local model loading or inference.
    """

    if not isinstance(features, dict):
        raise ValueError("Features must be a dictionary")

    # 1. Create AWS Lambda client
    client = boto3.client(
        "lambda",
        region_name=AWS_REGION,
        config=Config(
            connect_timeout=5,
            read_timeout=75
        )
    )

    # 2. Prepare request
    payload = {
        "features": features
    }

    # 3. Invoke Lambda synchronously
    try:
        response = client.invoke(
            FunctionName=LAMBDA_FUNCTION,
            InvocationType="RequestResponse",
            Payload=json.dumps(payload).encode("utf-8")
        )
    except NoCredentialsError as exc:
        raise RuntimeError(
            "AWS credentials are unavailable. "
            "Configure credentials or AWS_PROFILE before using cloud inference."
        ) from exc
    except ClientError as exc:
        error = exc.response.get("Error", {})
        code = error.get("Code", "Unknown")
        message = error.get("Message", str(exc))
        raise RuntimeError(
            f"AWS Lambda invocation error [{code}]: {message}"
        ) from exc

    # 4. Read Lambda response
    response_data = json.loads(
        response["Payload"].read()
    )

    # 5. Check Lambda execution errors
    if response.get("FunctionError"):
        error_type = response_data.get("errorType", "Unknown")
        error_message = response_data.get("errorMessage", "Unknown")

        raise RuntimeError(
            f"AWS Lambda error [{error_type}]: {error_message}"
        )
    # 6. Check invocation status
    if response["StatusCode"] != 200:
        raise RuntimeError(
            "Unexpected Lambda invocation status"
        )

    # 7. Validate response structure
    if not isinstance(response_data, dict):
        raise RuntimeError(
            "Invalid Lambda response"
        )

    required_fields = {
        "model_name",
        "no_show_score",
        "predicted_no_show",
        "threshold",
        "data_source"
    }

    if not required_fields.issubset(response_data):
        raise RuntimeError(
            "Lambda response is missing prediction fields"
        )

    return response_data
