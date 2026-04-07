"""
Aurora PostgreSQL connection management via RDS Proxy.
Handles connection pooling, SSL enforcement, and credential rotation.
"""

import json
import os
from contextlib import contextmanager
from typing import Generator

import boto3
import psycopg2
from psycopg2.extras import RealDictCursor

# Environment variables set by Terraform
DB_HOST = os.environ.get("DB_HOST")  # RDS Proxy endpoint
DB_PORT = int(os.environ.get("DB_PORT", "5432"))
DB_NAME = os.environ.get("DB_NAME", "unemployment_claims")
DB_SECRET_ARN = os.environ.get("DB_SECRET_ARN")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

_secrets_client = boto3.client("secretsmanager", region_name=AWS_REGION)


def _get_credentials() -> dict:
    """Retrieve database credentials from Secrets Manager."""
    response = _secrets_client.get_secret_value(SecretId=DB_SECRET_ARN)
    return json.loads(response["SecretString"])


@contextmanager
def get_connection(readonly: bool = False) -> Generator:
    """
    Context manager for Aurora PostgreSQL connections via RDS Proxy.

    RDS Proxy pools connections transparently -- Lambda functions should
    open and close connections per invocation. The proxy handles reuse.

    Args:
        readonly: If True, sets the transaction to read-only mode.
    """
    creds = _get_credentials()
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=creds["username"],
        password=creds["password"],
        sslmode="require",
        connect_timeout=5,
    )
    try:
        conn.autocommit = False
        if readonly:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def get_cursor(readonly: bool = False) -> Generator:
    """Convenience wrapper that yields a RealDictCursor."""
    with get_connection(readonly=readonly) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            yield cur
