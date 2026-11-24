
from app.core.cloud_db import get_cloud_connection


def create_tables():

    print("=== AWS CLINIC TABLE SETUP ===")

    with get_cloud_connection() as conn:

        # 1. Patients
        conn.execute("""
            CREATE TABLE IF NOT EXISTS patients (
                patient_id VARCHAR(20) PRIMARY KEY,
                name VARCHAR(150) NOT NULL
            )
        """)

        # 2. Doctors
        conn.execute("""
            CREATE TABLE IF NOT EXISTS doctors (
                doctor_id VARCHAR(20) PRIMARY KEY,
                name VARCHAR(150) NOT NULL,
                specialty VARCHAR(100) NOT NULL
            )
        """)

        # 3. Appointment slots
        conn.execute("""
            CREATE TABLE IF NOT EXISTS slots (
                slot_id VARCHAR(20) PRIMARY KEY,
                doctor_id VARCHAR(20) NOT NULL
                    REFERENCES doctors(doctor_id),
                date DATE NOT NULL,
                time TIME NOT NULL,
                status VARCHAR(20) NOT NULL
                    DEFAULT 'available'
                    CHECK (status IN ('available', 'booked')),
                UNIQUE (doctor_id, date, time)
            )
        """)

        # 4. Appointments
        conn.execute("""
            CREATE TABLE IF NOT EXISTS appointments (
                appointment_id VARCHAR(50) PRIMARY KEY,
                patient_id VARCHAR(20) NOT NULL
                    REFERENCES patients(patient_id),
                slot_id VARCHAR(20) NOT NULL
                    REFERENCES slots(slot_id),
                status VARCHAR(20) NOT NULL
                    CHECK (
                        status IN (
                            'booked',
                            'cancelled',
                            'rescheduled'
                        )
                    ),
                created_at TIMESTAMPTZ NOT NULL
                    DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Prevent duplicate active bookings
        conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
                one_active_booking_per_slot
            ON appointments(slot_id)
            WHERE status = 'booked'
        """)

        # 5. Historical attendance
        conn.execute("""
            CREATE TABLE IF NOT EXISTS attendance_history (
                history_id VARCHAR(50) PRIMARY KEY,
                patient_id VARCHAR(20) NOT NULL
                    REFERENCES patients(patient_id),
                appointment_date DATE NOT NULL,
                outcome VARCHAR(20) NOT NULL
                    CHECK (
                        outcome IN ('attended', 'no_show')
                    ),
                recorded_at TIMESTAMPTZ NOT NULL
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

        # 6. Appointment reminders
        conn.execute("""
            CREATE TABLE IF NOT EXISTS appointment_reminders (
                appointment_id VARCHAR(50) PRIMARY KEY
                    REFERENCES appointments(appointment_id),
                reminder_planned INTEGER NOT NULL
                    CHECK (reminder_planned IN (0, 1))
            )
        """)

        # Commit all schema changes
        conn.commit()

        tables = [
            "patients",
            "doctors",
            "slots",
            "appointments",
            "attendance_history",
            "appointment_reminders"
        ]

        print("\nCloud tables created successfully!")

        for table in tables:
            result = conn.execute(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                      AND table_name = %s
                ) AS exists
                """,
                (table,)
            ).fetchone()

            print(f"{table}: {result['exists']}")

        vector = conn.execute(
            """
            SELECT extversion
            FROM pg_extension
            WHERE extname = 'vector'
            """
        ).fetchone()

        print(
            "pgvector:",
            vector["extversion"] if vector else "NOT FOUND"
        )

        print("\nCLOUD DATABASE TABLE SETUP COMPLETED")


if __name__ == "__main__":
    create_tables()
