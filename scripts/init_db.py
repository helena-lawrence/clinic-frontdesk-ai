
import sqlite3
import csv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "clinic.db"
DATA_DIR = BASE_DIR / "data" / "synthetic"


def load_csv(filename):
    with open(DATA_DIR / filename, newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def create_database():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")

    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS patients (
                patient_id TEXT PRIMARY KEY,
                name TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS doctors (
                doctor_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                specialty TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS slots (
                slot_id TEXT PRIMARY KEY,
                doctor_id TEXT NOT NULL,
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'available'
                    CHECK(status IN ('available', 'booked')),
                FOREIGN KEY (doctor_id) REFERENCES doctors(doctor_id),
                UNIQUE(doctor_id, date, time)
            );

            CREATE TABLE IF NOT EXISTS appointments (
                appointment_id TEXT PRIMARY KEY,
                patient_id TEXT NOT NULL,
                slot_id TEXT NOT NULL,
                status TEXT NOT NULL
                    CHECK(status IN ('booked', 'cancelled', 'rescheduled')),
                created_at TEXT NOT NULL,
                FOREIGN KEY (patient_id) REFERENCES patients(patient_id),
                FOREIGN KEY (slot_id) REFERENCES slots(slot_id)
            );

            CREATE UNIQUE INDEX IF NOT EXISTS one_active_booking_per_slot
            ON appointments(slot_id)
            WHERE status = 'booked';
        """)

        patients = load_csv("patients.csv")
        doctors = load_csv("doctors.csv")
        slots = load_csv("slots.csv")

        with conn:
            conn.executemany(
                "INSERT OR IGNORE INTO patients VALUES (?, ?)",
                [(p["patient_id"], p["name"]) for p in patients]
            )

            conn.executemany(
                "INSERT OR IGNORE INTO doctors VALUES (?, ?, ?)",
                [
                    (d["doctor_id"], d["name"], d["specialty"])
                    for d in doctors
                ]
            )

            conn.executemany(
                "INSERT OR IGNORE INTO slots VALUES (?, ?, ?, ?, ?)",
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

        print("Database created successfully!")

        for table in ["patients", "doctors", "slots", "appointments"]:
            count = conn.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0]
            print(f"{table}: {count} records")

    finally:
        conn.close()


if __name__ == "__main__":
    create_database()
