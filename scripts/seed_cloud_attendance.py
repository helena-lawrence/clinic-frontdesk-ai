
import random

from datetime import date, datetime, timedelta, timezone

from app.core.cloud_db import get_cloud_connection


rng = random.Random(42)


def seed_cloud_attendance():

    print("=== AWS ATTENDANCE HISTORY SETUP ===")

    today = date.today()

    records = []

    # Generate historical records for 10 patients
    for patient_number in range(1, 11):

        patient_id = f"P{patient_number:03d}"

        for visit in range(1, 7):

            appointment_date = today - timedelta(
                days=180 - (visit * 20) + patient_number
            )

            # Synthetic attendance outcomes
            if patient_id == "P001":
                no_show = False

            elif patient_id == "P002":
                no_show = visit in (2, 4)

            else:
                no_show = rng.random() < 0.18

            outcome = (
                "no_show" if no_show else "attended"
            )

            recorded_at = datetime.combine(
                appointment_date + timedelta(days=1),
                datetime.min.time(),
                tzinfo=timezone.utc
            )

            records.append((
                f"DEMO-{patient_id}-{visit:02d}",
                patient_id,
                appointment_date,
                outcome,
                recorded_at
            ))

    # Connect directly to AWS PostgreSQL
    with get_cloud_connection() as conn:

        database = conn.execute(
            "SELECT current_database() AS name"
        ).fetchone()["name"]

        if database != "clinicdb":
            raise RuntimeError(
                "Expected AWS database clinicdb"
            )

        print(f"Connected to: {database}")

        # Check the required patients exist
        patient_count = conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM patients
            WHERE patient_id IN (
                'P001', 'P002', 'P003', 'P004', 'P005',
                'P006', 'P007', 'P008', 'P009', 'P010'
            )
            """
        ).fetchone()["total"]

        if patient_count != 10:
            raise RuntimeError(
                "All 10 synthetic patients must exist first"
            )

        # Import historical attendance
        with conn.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO attendance_history (
                    history_id,
                    patient_id,
                    appointment_date,
                    outcome,
                    recorded_at
                )
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (history_id) DO NOTHING
                """,
                records
            )

        # Verify imported records
        total = conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM attendance_history
            WHERE history_id LIKE 'DEMO-%'
            """
        ).fetchone()["total"]

        print(f"\nSynthetic attendance records: {total}")

        print("\nPatient attendance summary:")

        rows = conn.execute(
            """
            SELECT
                patient_id,
                COUNT(*) AS previous_appointments,
                COUNT(*) FILTER (
                    WHERE outcome = 'no_show'
                ) AS previous_no_shows
            FROM attendance_history
            WHERE history_id LIKE 'DEMO-%'
            GROUP BY patient_id
            ORDER BY patient_id
            """
        ).fetchall()

        for row in rows:
            print(
                f"{row['patient_id']}: "
                f"{row['previous_appointments']} appointments, "
                f"{row['previous_no_shows']} no-shows"
            )

        if total != 60:
            raise RuntimeError(
                "Expected exactly 60 synthetic records"
            )

    print("\nAWS ATTENDANCE HISTORY COMPLETED")


if __name__ == "__main__":
    seed_cloud_attendance()
