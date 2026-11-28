"""PostgreSQL connection adapter for Supabase, with SQLite retained for local tests.

Set DATABASE_URL on the backend to use Supabase. The API connects server-side;
database credentials must never be shipped to the browser.
"""
from __future__ import annotations

import os
import re
import sqlite3
from typing import Any


class Row(dict):
    """Mapping row that also supports SQLite-style integer indexing."""
    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class Cursor:
    def __init__(self, cursor, lastrowid=None):
        self._cursor = cursor
        self._lastrowid = lastrowid

    @property
    def rowcount(self):
        return self._cursor.rowcount

    @property
    def lastrowid(self):
        if self._lastrowid is None and self._cursor.description:
            row = self._cursor.fetchone()
            if row is not None:
                self._lastrowid = row["id"]
        return self._lastrowid

    def fetchone(self):
        row = self._cursor.fetchone()
        return Row(row) if row is not None and isinstance(row, dict) else row

    def fetchall(self):
        return [Row(row) if isinstance(row, dict) else row for row in self._cursor.fetchall()]


class Connection:
    def __init__(self, connection):
        self._connection = connection

    def execute(self, sql: str, params=()):
        statement = sql.strip()
        if statement.upper() == "BEGIN IMMEDIATE":
            statement = "BEGIN"
        statement = re.sub(r"\\bINTEGER\\s+PRIMARY\\s+KEY\\s+AUTOINCREMENT\\b", "BIGSERIAL PRIMARY KEY", statement, flags=re.I)
        ignore_insert = bool(re.match(r"INSERT\\s+OR\\s+IGNORE\\s+INTO\\s+", statement, flags=re.I))
        if ignore_insert:
            statement = re.sub(r"^INSERT\\s+OR\\s+IGNORE\\s+INTO", "INSERT INTO", statement, flags=re.I)
            statement += " ON CONFLICT DO NOTHING"
        # These tables use generated integer IDs and the application reads
        # cursor.lastrowid after inserts, matching SQLite's existing contract.
        match = re.match(r"INSERT\\s+INTO\\s+(trades|monitoring_events|thesis_reassessments|thesis_alerts)\\b", statement, flags=re.I)
        if match and not re.search(r"\\bRETURNING\\b", statement, flags=re.I):
            statement += " RETURNING id"
        statement = statement.replace("?", "%s")
        cursor = self._connection.execute(statement, params)
        return Cursor(cursor)

    def commit(self):
        self._connection.commit()

    def rollback(self):
        self._connection.rollback()

    def close(self):
        self._connection.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type is None:
                self.commit()
            else:
                self.rollback()
        finally:
            self.close()


def connect_postgres() -> Connection:
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL is required for the Supabase PostgreSQL connection.")
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as exc:
        raise RuntimeError("PostgreSQL support is missing. Install backend requirements.") from exc
    connection = psycopg.connect(
        database_url,
        row_factory=dict_row,
        options="-c search_path=app,public",
        connect_timeout=15,
    )
    return Connection(connection)


def using_postgres() -> bool:
    return bool(os.getenv("DATABASE_URL", "").strip())


def connect_sqlite(path: str, timeout: int = 10):
    connection = sqlite3.connect(path, timeout=timeout)
    connection.row_factory = sqlite3.Row
    return connection
