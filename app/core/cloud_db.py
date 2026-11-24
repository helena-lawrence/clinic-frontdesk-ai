
import os
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[2]

load_dotenv(BASE_DIR / ".env")

SSL_CERT = BASE_DIR / "certs" / "global-bundle.pem"


def get_cloud_connection():
    """Connect securely to AWS RDS PostgreSQL."""

    if not SSL_CERT.is_file():
        raise FileNotFoundError(
            "AWS RDS SSL certificate not found"
        )

    return psycopg.connect(
        host=os.environ["DB_HOST"],
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        sslmode="verify-full",
        sslrootcert=str(SSL_CERT),
        connect_timeout=10,
        row_factory=dict_row
    )
