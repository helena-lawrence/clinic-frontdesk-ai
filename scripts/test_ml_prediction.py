
from app.ml.predict import predict_no_show


print("=== CLINIC NO-SHOW PREDICTION TEST ===")

# Scenario 1: Patient with no previous missed appointments
patient_1 = {
    "lead_time_days": 2,
    "day_of_week": 0,
    "appointment_hour": 10,
    "reminder_planned": 1,
    "previous_appointments": 5,
    "previous_no_shows": 0
}

result_1 = predict_no_show(patient_1)

print("\nScenario 1: Patient with good attendance history")
print(result_1)


# Scenario 2: Patient with previous missed appointments
patient_2 = {
    "lead_time_days": 21,
    "day_of_week": 4,
    "appointment_hour": 9,
    "reminder_planned": 0,
    "previous_appointments": 5,
    "previous_no_shows": 3
}

result_2 = predict_no_show(patient_2)

print("\nScenario 2: Patient with previous no-shows")
print(result_2)


# Verify the service returns valid predictions
for result in [result_1, result_2]:
    assert 0 <= result["no_show_score"] <= 1
    assert isinstance(result["predicted_no_show"], bool)

print("\nML PREDICTION SERVICE TEST PASSED")
