
from functools import lru_cache
from pathlib import Path

import joblib
import pandas as pd


MODEL_PATH = Path(__file__).resolve().parent / "no_show_model.joblib"

FEATURES = [
    "lead_time_days",
    "day_of_week",
    "appointment_hour",
    "reminder_planned",
    "previous_appointments",
    "previous_no_shows"
]


@lru_cache(maxsize=1)
def load_model():
    """Load the model bundled inside the Lambda image."""

    if not MODEL_PATH.is_file():
        raise FileNotFoundError(
            f"Bundled ML model not found: {MODEL_PATH}"
        )

    artifact = joblib.load(MODEL_PATH)

    if artifact["features"] != FEATURES:
        raise RuntimeError("Model feature schema mismatch")

    return artifact


def validate_features(features):

    if not isinstance(features, dict):
        raise ValueError("Features must be a dictionary")

    if set(features) != set(FEATURES):
        raise ValueError("Incorrect ML feature names")

    for name in FEATURES:
        if type(features[name]) is not int:
            raise ValueError(f"{name} must be an integer")

    if not 1 <= features["lead_time_days"] <= 28:
        raise ValueError("Invalid lead time")

    if features["day_of_week"] not in range(5):
        raise ValueError("Invalid weekday")

    if features["appointment_hour"] not in (9, 10, 14, 15):
        raise ValueError("Invalid appointment hour")

    if features["reminder_planned"] not in (0, 1):
        raise ValueError("Invalid reminder value")

    previous = features["previous_appointments"]
    missed = features["previous_no_shows"]

    if previous < 0 or not 0 <= missed <= previous:
        raise ValueError("Invalid attendance history")


def lambda_handler(event, context):
    """Run ML inference entirely inside AWS Lambda."""

    if not isinstance(event, dict):
        raise ValueError("Invalid request")

    features = event.get("features")
    validate_features(features)

    artifact = load_model()
    model = artifact["model"]

    input_data = pd.DataFrame(
        [[features[name] for name in FEATURES]],
        columns=FEATURES
    )

    score = float(
        model.predict_proba(input_data)[0, 1]
    )

    threshold = float(artifact.get("threshold", 0.5))

    return {
        "model_name": artifact["model_name"],
        "no_show_score": round(score, 4),
        "predicted_no_show": bool(score >= threshold),
        "threshold": threshold,
        "data_source": "synthetic"
    }
