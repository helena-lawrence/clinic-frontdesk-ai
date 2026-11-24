
import csv
from pathlib import Path

from app.core.cloud_db import get_cloud_connection


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "synthetic"


def load_csv(filename):
    """Read existing synthetic CSV data."""

    file_path = DATA_DIR / filename

    if not file_path.exists():
        raise FileNotFoundError(
            f"Missing synthetic data file: {filename}"
        )

    with open(
        file_path,
        "r",
        encoding="utf-8",
        newline=""
    ) as file:
        return list(csv.DictReader(file))


def seed_cloud_database():

    print("=== AWS CLINIC DATA IMPORT ===")

    # 1. Load existing synthetic data
    patients = load_csv("patients.csv")
    doctors = load_csv("doctors.csv")
    slots = load_csv("slots.csv")

    print(f"Patients loaded: {len(patients)}")
    print(f"Doctors loaded: {len(doctors)}")
    print(f"Slots loaded: {len(slots)}")

    # 2. Connect directly to AWS RDS
    with get_cloud_connection() as conn:

        database = conn.execute(
            "SELECT current_database() AS name"
        ).fetchone()["name"]

        if database != "clinicdb":
            raise RuntimeError(
                f"Expected clinicdb, connected to {database}"
            )

        print(f"\nConnected to AWS database: {database}")

        # 3. Import patients
        with conn.cursor() as cursor:

            cursor.executemany(
                """
                INSERT INTO patients (patient_id, name)
                VALUES (%s, %s)
                ON CONFLICT (patient_id) DO NOTHING
                """,
                [
                    (p["patient_id"], p["name"])
                    for p in patients
                ]
            )

            print("Patients imported")

            # 4. Import doctors
            cursor.executemany(
                """
                INSERT INTO doctors
                (doctor_id, name, specialty)
                VALUES (%s, %s, %s)
                ON CONFLICT (doctor_id) DO NOTHING
                """,
                [
                    (
                        d["doctor_id"],
                        d["name"],
                        d["specialty"]
                    )
                    for d in doctors
                ]
            )

            print("Doctors imported")

            # 5. Import appointment slots
            cursor.executemany(
                """
                INSERT INTO slots
                (slot_id, doctor_id, date, time, status)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (slot_id) DO NOTHING
                """,
                [
                    (
                        s["slot_id"],
                        s["doctor_id"],
                        s["date"],
                        s["time"],
                        s["status"]
                    )
                    for s in slots
                ]
            )

            print("Appointment slots imported")

        # 6. Commit all records together
        conn.commit()

        # 7. Verify database record counts
        print("\n=== AWS DATABASE VERIFICATION ===")

        tables = [
            "patients",
            "doctors",
            "slots",
            "appointments"
        ]

        for table in tables:

            result = conn.execute(
                f"SELECT COUNT(*) AS total FROM {table}"
            ).fetchone()

            print(f"{table}: {result['total']} records")

    print("\nAWS SYNTHETIC DATA IMPORT COMPLETED")


if __name__ == "__main__":
    seed_cloud_database()
