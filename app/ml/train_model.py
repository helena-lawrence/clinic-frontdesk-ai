
import joblib
import pandas as pd

from pathlib import Path

from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier

from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    confusion_matrix
)

# Project paths
BASE_DIR = Path(__file__).resolve().parents[2]

DATA_PATH = (
    BASE_DIR / "data" / "processed" / "no_show_training.csv"
)

MODEL_DIR = BASE_DIR / "app" / "ml" / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

MODEL_PATH = MODEL_DIR / "no_show_model.joblib"

# Features available at prediction time
FEATURES = [
    "lead_time_days",
    "day_of_week",
    "appointment_hour",
    "reminder_planned",
    "previous_appointments",
    "previous_no_shows"
]

TARGET = "no_show"


def load_dataset():
    df = pd.read_csv(
        DATA_PATH,
        parse_dates=["booking_date", "appointment_date"]
    )

    print(f"Total records: {len(df)}")
    print("\nTarget distribution:")
    print(df[TARGET].value_counts())

    return df.sort_values("appointment_date").reset_index(drop=True)


def split_dataset(df):
    """
    Chronological split to reduce future information leakage.

    Training outcomes must be known before validation begins.
    Validation outcomes must be known before testing begins.
    """

    first_cutoff = df["appointment_date"].iloc[int(len(df) * 0.70)]
    second_cutoff = df["appointment_date"].iloc[int(len(df) * 0.85)]

    train = df[
        df["appointment_date"] < first_cutoff
    ].copy()

    valid = df[
        (df["booking_date"] >= first_cutoff) &
        (df["appointment_date"] < second_cutoff)
    ].copy()

    test = df[
        df["booking_date"] >= second_cutoff
    ].copy()

    for name, subset in [
        ("Training", train),
        ("Validation", valid),
        ("Testing", test)
    ]:
        if subset.empty or subset[TARGET].nunique() != 2:
            raise ValueError(
                f"{name} data needs both attended and no-show records"
            )

    print("\nDataset split:")
    print(f"Training:   {len(train)}")
    print(f"Validation: {len(valid)}")
    print(f"Testing:    {len(test)}")

    return train, valid, test


def build_models():
    models = {
        "Logistic Regression": Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            ("classifier", LogisticRegression(
                max_iter=1000,
                class_weight="balanced",
                random_state=42
            ))
        ]),

        "Random Forest": Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("classifier", RandomForestClassifier(
                n_estimators=200,
                min_samples_leaf=5,
                class_weight="balanced",
                random_state=42,
                n_jobs=-1
            ))
        ])
    }

    return models


def evaluate_model(model, X, y):
    predictions = model.predict(X)
    probabilities = model.predict_proba(X)[:, 1]

    return {
        "accuracy": accuracy_score(y, predictions),
        "precision": precision_score(
            y, predictions, zero_division=0
        ),
        "recall": recall_score(
            y, predictions, zero_division=0
        ),
        "f1": f1_score(
            y, predictions, zero_division=0
        ),
        "roc_auc": roc_auc_score(y, probabilities),
        "confusion_matrix": confusion_matrix(
            y, predictions, labels=[0, 1]
        )
    }


def print_metrics(metrics):
    for metric in [
        "accuracy",
        "precision",
        "recall",
        "f1",
        "roc_auc"
    ]:
        print(f"{metric}: {metrics[metric]:.4f}")


def train_model():
    print("=== ML NO-SHOW TRAINING ===")

    df = load_dataset()

    train, valid, test = split_dataset(df)

    X_train = train[FEATURES]
    y_train = train[TARGET]

    X_valid = valid[FEATURES]
    y_valid = valid[TARGET]

    models = build_models()

    validation_results = {}

    # Train and compare both models
    for name, model in models.items():
        print(f"\nTraining {name}...")

        model.fit(X_train, y_train)

        metrics = evaluate_model(
            model, X_valid, y_valid
        )

        validation_results[name] = metrics

        print(f"\n{name} validation results:")
        print_metrics(metrics)

    # Select by F1, then ROC-AUC as a tie-breaker
    best_name = max(
        validation_results,
        key=lambda name: (
            validation_results[name]["f1"],
            validation_results[name]["roc_auc"]
        )
    )

    print(f"\nSelected model: {best_name}")

    # Retrain selected model with training + validation data
    combined = pd.concat(
        [train, valid],
        ignore_index=True
    )

    best_model = build_models()[best_name]

    best_model.fit(
        combined[FEATURES],
        combined[TARGET]
    )

    # Final evaluation on untouched test period
    test_metrics = evaluate_model(
        best_model,
        test[FEATURES],
        test[TARGET]
    )

    print("\n=== FINAL TEST RESULTS ===")
    print_metrics(test_metrics)

    print("\nConfusion Matrix:")
    print(test_metrics["confusion_matrix"])

    # Save model and feature configuration
    artifact = {
        "model": best_model,
        "features": FEATURES,
        "model_name": best_name,
        "threshold": 0.5,
        "data_source": "synthetic"
    }

    joblib.dump(artifact, MODEL_PATH)

    print(f"\nModel saved successfully: {MODEL_PATH}")


if __name__ == "__main__":
    train_model()
