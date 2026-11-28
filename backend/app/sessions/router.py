"""Persistent, single-user market-session lifecycle.

Sessions describe which public market symbols the frontend may poll. There are
no server-side provider streams to leak: browser polling is enabled only while
the persisted session is ACTIVE and is torn down on stop/expiry.
"""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])
DB_PATH = os.getenv("SESSION_DB_PATH", "data/sessions.sqlite3")
MAX_SESSION_HOURS = 8
DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "NVDA", "AAPL", "GOOGL"]
SYMBOL_PROVIDERS = {
    "BTCUSDT": "binance",
    "ETHUSDT": "binance",
    "SOLUSDT": "binance",
    "NVDA": "twelvedata",
    "AAPL": "twelvedata",
    "GOOGL": "twelvedata",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS market_sessions (
            id TEXT PRIMARY KEY,
            status TEXT NOT NULL CHECK(status IN ('ACTIVE','STOPPED','EXPIRED')),
            started_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            ended_at TEXT,
            interval TEXT NOT NULL,
            symbols_json TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def _expire_active(conn: sqlite3.Connection, now: datetime) -> None:
    conn.execute(
        "UPDATE market_sessions SET status='EXPIRED', ended_at=? "
        "WHERE status='ACTIVE' AND expires_at<=?",
        (now.isoformat(), now.isoformat()),
    )


def _serialize(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    return {
        "id": row["id"],
        "status": row["status"],
        "started_at": row["started_at"],
        "expires_at": row["expires_at"],
        "ended_at": row["ended_at"],
        "interval": row["interval"],
        "subscriptions": json.loads(row["symbols_json"]),
        "maximum_duration_hours": MAX_SESSION_HOURS,
    }


class SessionStart(BaseModel):
    symbols: list[str] = Field(default_factory=lambda: DEFAULT_SYMBOLS.copy(), min_length=1, max_length=6)
    interval: Literal["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w", "1M"] = "1h"


@router.get("/current")
async def current_session() -> dict:
    now = _now()
    with _connect() as conn:
        _expire_active(conn, now)
        row = conn.execute(
            "SELECT * FROM market_sessions WHERE status='ACTIVE' ORDER BY started_at DESC LIMIT 1"
        ).fetchone()
        return {"active": row is not None, "session": _serialize(row), "maximum_duration_hours": MAX_SESSION_HOURS}


@router.post("/start")
async def start_session(request: SessionStart) -> dict:
    symbols = [symbol.strip().upper() for symbol in request.symbols]
    if len(set(symbols)) != len(symbols):
        raise HTTPException(status_code=422, detail="Session subscriptions must not contain duplicate symbols.")
    unsupported = [symbol for symbol in symbols if symbol not in SYMBOL_PROVIDERS]
    if unsupported:
        raise HTTPException(status_code=422, detail=f"Unsupported session symbol(s): {', '.join(unsupported)}.")

    now = _now()
    expires = now + timedelta(hours=MAX_SESSION_HOURS)
    session_id = str(uuid.uuid4())
    subscriptions = [
        {"symbol": symbol, "provider": SYMBOL_PROVIDERS[symbol]}
        for symbol in symbols
    ]
    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        _expire_active(conn, now)
        active = conn.execute(
            "SELECT id FROM market_sessions WHERE status='ACTIVE' LIMIT 1"
        ).fetchone()
        if active:
            raise HTTPException(status_code=409, detail="A market session is already active. Stop it before starting another.")
        conn.execute(
            "INSERT INTO market_sessions (id,status,started_at,expires_at,interval,symbols_json) "
            "VALUES (?,?,?,?,?,?)",
            (session_id, "ACTIVE", now.isoformat(), expires.isoformat(), request.interval, json.dumps(subscriptions)),
        )
        row = conn.execute("SELECT * FROM market_sessions WHERE id=?", (session_id,)).fetchone()
        return {"active": True, "session": _serialize(row), "maximum_duration_hours": MAX_SESSION_HOURS}


@router.post("/{session_id}/stop")
async def stop_session(session_id: str) -> dict:
    now = _now()
    with _connect() as conn:
        _expire_active(conn, now)
        row = conn.execute("SELECT * FROM market_sessions WHERE id=?", (session_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Session not found.")
        if row["status"] == "ACTIVE":
            conn.execute(
                "UPDATE market_sessions SET status='STOPPED', ended_at=? WHERE id=? AND status='ACTIVE'",
                (now.isoformat(), session_id),
            )
            row = conn.execute("SELECT * FROM market_sessions WHERE id=?", (session_id,)).fetchone()
        return {"active": False, "session": _serialize(row), "maximum_duration_hours": MAX_SESSION_HOURS}


@router.get("/history")
async def session_history() -> dict:
    now = _now()
    with _connect() as conn:
        _expire_active(conn, now)
        rows = conn.execute("SELECT * FROM market_sessions ORDER BY started_at DESC LIMIT 50").fetchall()
        return {"sessions": [_serialize(row) for row in rows], "maximum_duration_hours": MAX_SESSION_HOURS}
