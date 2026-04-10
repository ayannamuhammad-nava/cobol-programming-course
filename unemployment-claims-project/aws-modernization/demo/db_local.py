"""
Local database connection module for demo purposes.
Uses SQLite instead of Aurora PostgreSQL so the demo runs with zero
external dependencies -- no Docker, no AWS, no pip installs needed.

The Lambda handlers use psycopg2-style parameterized queries (%s placeholders)
and dict-cursor access (row["column"]). This module provides a thin
compatibility layer that translates those patterns to SQLite.
"""

import os
import sqlite3
from contextlib import contextmanager
from typing import Generator

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "claims_demo.db")


class DictRow(dict):
    """A dict that also supports index-based access like a psycopg2 tuple row."""
    def __init__(self, keys, values):
        super().__init__(zip(keys, values))
        self._values = list(values)

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        return super().__getitem__(key)


class DictCursor:
    """Wraps a sqlite3.Cursor to return DictRow objects and accept %s params."""

    def __init__(self, conn):
        self._conn = conn
        self._cursor = conn.cursor()
        self.description = None

    def execute(self, sql, params=None):
        # Translate %s placeholders to ? for SQLite
        sql = sql.replace("%s", "?")
        # Remove/translate PostgreSQL-specific syntax for SQLite
        import re
        sql = re.sub(r'\s+FOR\s+UPDATE\b', '', sql, flags=re.IGNORECASE)
        sql = re.sub(r'\s+SET\s+TRANSACTION\s+READ\s+ONLY\b', '', sql, flags=re.IGNORECASE)
        # Translate boolean literals
        sql = re.sub(r'\bTRUE\b', '1', sql)
        sql = re.sub(r'\bFALSE\b', '0', sql)
        if params:
            self._cursor.execute(sql, params)
        else:
            self._cursor.execute(sql)
        self.description = self._cursor.description
        return self

    def fetchone(self):
        row = self._cursor.fetchone()
        if row is None or self.description is None:
            return None
        keys = [d[0] for d in self.description]
        return DictRow(keys, row)

    def fetchall(self):
        rows = self._cursor.fetchall()
        if not rows or self.description is None:
            return []
        keys = [d[0] for d in self.description]
        return [DictRow(keys, row) for row in rows]

    def close(self):
        self._cursor.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class ConnectionWrapper:
    """Wraps sqlite3.Connection with a psycopg2-compatible interface."""

    def __init__(self, conn):
        self._conn = conn

    def cursor(self, cursor_factory=None):
        return DictCursor(self._conn)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


@contextmanager
def get_connection(readonly: bool = False) -> Generator:
    """Context manager that opens a local SQLite connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    wrapper = ConnectionWrapper(conn)
    try:
        yield wrapper
        if not readonly:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def get_cursor(readonly: bool = False) -> Generator:
    """Convenience wrapper that yields a dict-cursor."""
    with get_connection(readonly=readonly) as conn:
        cur = conn.cursor()
        try:
            yield cur
        finally:
            cur.close()
