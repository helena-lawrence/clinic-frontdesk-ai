
import sqlite3
import random

from pathlib import Path
from datetime import date, datetime, timedelta, timezone

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "clinic.db"

rng = random.Random(42)


def seed_attendance_history():

    if not DB_PATH.exists():
        raise FileNotFoundError("Clinic database not found")

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")

    today = date.today()

    records = []

    for patient_number in range(1, 11):

        patient_id = f"P{patient_number:03d}"

        for visit in range(1, 7):

            # All appointments are historical
            appointment_date = today - timedelta(
                days=180 - (visit * 20) + patient_number
            )

            # Controlled synthetic attendance outcomes
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
            ).isoformat()

            records.append((
                f"DEMO-{patient_id}-{visit:02d}",
                patient_id,
                appointment_date.isoformat(),
                outcome,
                recorded_at
            ))

    try:
        with conn:
            before = conn.total_changes

            conn.executemany(
                """
                INSERT OR IGNORE INTO attendance_history
                (
                    history_id,
                    patient_id,
                    appointment_date,
                    outcome,
                    recorded_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                records
            )

            inserted = conn.total_changes - before

        print("Attendance history setup completed!")
        print(f"New records inserted: {inserted}")

        print("\nPatient attendance summary:")

        rows = conn.execute(
            """
            SELECT
                patient_id,
                COUNT(*) AS previous_appointments,
                SUM(
                    CASE WHEN outcome = 'no_show'
                    THEN 1 ELSE 0 END
                ) AS previous_no_shows
            FROM attendance_history
            WHERE history_id LIKE 'DEMO-%'
            GROUP BY patient_id
            ORDER BY patient_id
            """
        ).fetchall()

        for patient_id, total, missed in rows:
            print(
                f"{patient_id}: "
                f"{total} appointments, "
                f"{missed} no-shows"
            )

    finally:
        conn.close()


if __name__ == "__main__":
    seed_attendance_history()
