
import os
from pathlib import Path

import psycopg
from psycopg import sql
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DB_NAME = "clinicdb"

connection_config = {
    "host": os.environ["DB_HOST"],
    "port": int(os.getenv("DB_PORT", "5432")),
    "user": os.environ["DB_USER"],
    "password": os.environ["DB_PASSWORD"],
    "sslmode": "verify-full",
    "sslrootcert": str(
        BASE_DIR / "certs" / "global-bundle.pem"
    ),
    "connect_timeout": 10
}


def setup_database():

    print("=== AWS CLINIC DATABASE SETUP ===")

    # Step 1: Create a dedicated clinic database
    with psycopg.connect(
        dbname="postgres",
        autocommit=True,
        **connection_config
    ) as conn:

        exists = conn.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s",
            (DB_NAME,)
        ).fetchone()

        if not exists:
            conn.execute(
                sql.SQL("CREATE DATABASE {}").format(
                    sql.Identifier(DB_NAME)
                )
            )
            print("Created database: clinicdb")
        else:
            print("Database clinicdb already exists")

    # Step 2: Enable pgvector in clinicdb
    with psycopg.connect(
        dbname=DB_NAME,
        **connection_config
    ) as conn:

        available = conn.execute(
            """
            SELECT default_version
            FROM pg_available_extensions
            WHERE name = 'vector'
            """
        ).fetchone()

        if not available:
            raise RuntimeError(
                "pgvector is not available on this "
                "RDS PostgreSQL version"
            )

        conn.execute(
            "CREATE EXTENSION IF NOT EXISTS vector"
        )

        version = conn.execute(
            """
            SELECT extversion
            FROM pg_extension
            WHERE extname = 'vector'
            """
        ).fetchone()

        if not version:
            raise RuntimeError("pgvector installation failed")

        # Test the vector data type
        result = conn.execute(
            "SELECT '[1,2,3]'::vector"
        ).fetchone()

        print("pgvector version:", version[0])
        print("Test vector:", result[0])
        print("Cloud database setup successful!")


if __name__ == "__main__":
    setup_database()
