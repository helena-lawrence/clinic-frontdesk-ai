
from app.ml.cloud_inference import (
    predict_no_show_cloud
)


print("=== AWS CLOUD ML INFERENCE TEST ===")

# Synthetic test appointment
features = {
    "lead_time_days": 21,
    "day_of_week": 4,
    "appointment_hour": 9,
    "reminder_planned": 0,
    "previous_appointments": 5,
    "previous_no_shows": 3
}

print("\nSending features to AWS Lambda...")

result = predict_no_show_cloud(features)

print("\nPrediction received from AWS:")
print("Model:", result["model_name"])
print("No-show score:", result["no_show_score"])
print("Predicted no-show:", result["predicted_no_show"])
print("Threshold:", result["threshold"])
print("Data source:", result["data_source"])

assert 0 <= result["no_show_score"] <= 1
assert isinstance(result["predicted_no_show"], bool)

print("\nAWS CLOUD ML INFERENCE TEST PASSED")
