
from app.ml.cloud_features import (
    get_cloud_appointment_features
)

from app.ml.cloud_inference import (
    predict_no_show_cloud
)


def predict_appointment_risk(patient_id, appointment_id):
    """
    Retrieve appointment features from AWS RDS
    and perform inference using AWS Lambda.
    """

    # Step 1: Get features from cloud database
    features = get_cloud_appointment_features(
        patient_id=patient_id,
        appointment_id=appointment_id
    )

    # Step 2: Send features to AWS Lambda
    prediction = predict_no_show_cloud(features)

    # Step 3: Return the combined result
    return {
        "appointment_id": appointment_id,
        "features": features,
        "prediction": prediction
    }
