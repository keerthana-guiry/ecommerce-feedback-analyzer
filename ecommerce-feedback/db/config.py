"""
MySQL connection settings and the shared connection pool.
Settings come from environment variables, usually from the .env file that
setup_database.py creates in the project folder.
"""

import os
from contextlib import contextmanager

from dotenv import load_dotenv
from mysql.connector import pooling

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ENV_FILE = os.path.join(PROJECT_ROOT, ".env")
SCHEMA_FILE = os.path.join(os.path.dirname(__file__), "schema.sql")

load_dotenv(ENV_FILE)

_pool = None


def connection_settings(database=None):
    return {
        "host": os.environ.get("DB_HOST", "localhost"),
        "port": int(os.environ.get("DB_PORT", "3306")),
        "user": os.environ.get("DB_USER", "feedback_app"),
        "password": os.environ.get("DB_PASSWORD", ""),
        "database": database or os.environ.get("DB_NAME", "ecommerce_feedback"),
    }


def _get_pool():
    global _pool
    if _pool is None:
        _pool = pooling.MySQLConnectionPool(pool_name="feedback", pool_size=5, **connection_settings())
    return _pool


@contextmanager
def get_cursor(commit=False):
    """Give a cursor whose rows are dicts. With commit=True, everything done
    inside the `with` block is saved together, or undone if an error occurs."""
    connection = _get_pool().get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        yield cursor
        if commit:
            connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def apply_schema(connection):
    """Create any missing tables from schema.sql on an open connection."""
    with open(SCHEMA_FILE, encoding="utf-8") as schema_file:
        lines = [line for line in schema_file if not line.lstrip().startswith("--")]

    cursor = connection.cursor()
    for statement in "".join(lines).split(";"):
        if statement.strip():
            cursor.execute(statement)
    connection.commit()
    cursor.close()
