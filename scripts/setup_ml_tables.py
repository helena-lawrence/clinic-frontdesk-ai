
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "clinic.db"


def setup_ml_tables():

    if not DB_PATH.is_file():
        raise FileNotFoundError(
            "Clinic database not found. Run init_db.py first."
        )

    conn = sqlite3.connect(DB_PATH)

    try:
        conn.execute("PRAGMA foreign_keys = ON")

        with conn:
            # Historical appointment attendance
            conn.execute("""
                CREATE TABLE IF NOT EXISTS attendance_history (
                    history_id TEXT PRIMARY KEY,
                    patient_id TEXT NOT NULL,
                    appointment_date TEXT NOT NULL,
                    outcome TEXT NOT NULL
                        CHECK(outcome IN ('attended', 'no_show')),
                    recorded_at TEXT NOT NULL,

                    FOREIGN KEY(patient_id)
                        REFERENCES patients(patient_id)
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS
                    idx_attendance_patient_date
                ON attendance_history(
                    patient_id,
                    appointment_date
                )
            """)

            # Appointment reminder information
            conn.execute("""
                CREATE TABLE IF NOT EXISTS appointment_reminders (
                    appointment_id TEXT PRIMARY KEY,
                    reminder_planned INTEGER NOT NULL
                        CHECK(reminder_planned IN (0, 1)),

                    FOREIGN KEY(appointment_id)
                        REFERENCES appointments(appointment_id)
                )
            """)

        print("ML database tables created successfully!")

        for table in [
            "attendance_history",
            "appointment_reminders"
        ]:
            count = conn.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0]

            print(f"{table}: {count} records")

    finally:
        conn.close()


if __name__ == "__main__":
    setup_ml_tables()
