
from functools import lru_cache
from pathlib import Path

import joblib
import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[2]

MODEL_PATH = (
    BASE_DIR / "app" / "ml" / "models" / "no_show_model.joblib"
)


@lru_cache(maxsize=1)
def load_model():
    """Load the trained model once and reuse it."""

    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            "Trained ML model not found. "
            "Run the training script first."
        )

    # Only load model files produced by our trusted training script
    artifact = joblib.load(MODEL_PATH)

    return artifact


def validate_features(features):
    """Validate appointment details before prediction."""

    if not isinstance(features, dict):
        raise ValueError("Features must be a dictionary")

    expected = set(load_model()["features"])

    if set(features) != expected:
        raise ValueError(
            f"Expected exactly these features: {sorted(expected)}"
        )

    for name, value in features.items():
        if type(value) is not int:
            raise ValueError(f"{name} must be an integer")

    if not 1 <= features["lead_time_days"] <= 28:
        raise ValueError("Lead time must be between 1 and 28 days")

    if features["day_of_week"] not in range(5):
        raise ValueError("Only Monday to Friday are supported")

    if features["appointment_hour"] not in (9, 10, 14, 15):
        raise ValueError("Unsupported appointment hour")

    if features["reminder_planned"] not in (0, 1):
        raise ValueError("Reminder must be 0 or 1")

    previous = features["previous_appointments"]
    missed = features["previous_no_shows"]

    if previous < 0 or missed < 0 or missed > previous:
        raise ValueError("Invalid appointment history")


def predict_no_show(features):
    """
    Predict appointment no-show using the trained ML model.
    """

    validate_features(features)

    artifact = load_model()

    model = artifact["model"]
    feature_names = artifact["features"]
    threshold = artifact["threshold"]

    # Preserve the exact feature order used during training
    input_data = pd.DataFrame(
        [[features[name] for name in feature_names]],
        columns=feature_names
    )

    # Class 1 represents a no-show
    score = float(
        model.predict_proba(input_data)[0, 1]
    )

    predicted_no_show = score >= threshold

    return {
        "model_name": artifact["model_name"],
        "no_show_score": round(score, 4),
        "predicted_no_show": predicted_no_show,
        "threshold": threshold,
        "data_source": artifact["data_source"]
    }
