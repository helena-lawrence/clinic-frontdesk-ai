
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

SSL_CERT = BASE_DIR / "certs" / "global-bundle.pem"


def test_connection():

    print("=== AWS RDS POSTGRESQL CONNECTION TEST ===")

    if not SSL_CERT.is_file():
        raise FileNotFoundError(
            "AWS RDS SSL certificate not found"
        )

    required = [
        "DB_HOST",
        "DB_NAME",
        "DB_USER",
        "DB_PASSWORD"
    ]

    for name in required:
        if not os.getenv(name):
            raise ValueError(
                f"Missing environment variable: {name}"
            )

    print("Connecting to AWS PostgreSQL...")

    with psycopg.connect(
        host=os.environ["DB_HOST"],
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        sslmode="verify-full",
        sslrootcert=str(SSL_CERT),
        connect_timeout=10
    ) as conn:

        with conn.cursor() as cursor:

            cursor.execute("""
                SELECT
                    current_database(),
                    current_user,
                    current_setting('server_version')
            """)

            db_name, db_user, version = cursor.fetchone()

            cursor.execute("""
                SELECT ssl
                FROM pg_stat_ssl
                WHERE pid = pg_backend_pid()
            """)

            tls_enabled = cursor.fetchone()[0]

            if not tls_enabled:
                raise RuntimeError(
                    "Database connection is not encrypted"
                )

            print("\nCONNECTION SUCCESSFUL!")
            print("Database:", db_name)
            print("User:", db_user)
            print("PostgreSQL version:", version)
            print("TLS encryption:", tls_enabled)


if __name__ == "__main__":
    test_connection()
