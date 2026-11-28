"""Snapshot-driven monitoring for manually registered trades.

This service raises alerts only. It never closes trades or places broker orders.
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from typing import Literal

import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1/monitoring", tags=["monitoring"])
DB_PATH = os.getenv("TRADING_DB_PATH", "data/trade_desk.sqlite3")
MAX_SNAPSHOT_AGE_SECONDS = int(os.getenv("MONITORING_MAX_SNAPSHOT_AGE_SECONDS", "300"))


def _connect():
    folder = os.path.dirname(DB_PATH)
    if folder:
        os.makedirs(folder, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("""CREATE TABLE IF NOT EXISTS monitoring_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trade_id INTEGER NOT NULL,
        symbol TEXT NOT NULL,
        event_type TEXT NOT NULL,
        observed_price REAL NOT NULL,
        source TEXT NOT NULL,
        market_data_timestamp TEXT NOT NULL,
        delivery_status TEXT NOT NULL DEFAULT 'pending',
        delivery_attempts INTEGER NOT NULL DEFAULT 0,
        last_error TEXT,
        created_at TEXT NOT NULL,
        delivered_at TEXT,
        UNIQUE(trade_id, event_type)
    )""")
    conn.commit()
    return conn


class PriceSnapshot(BaseModel):
    symbol: str = Field(min_length=1, max_length=30)
    current_price: float = Field(gt=0, le=1e15)
    market_data_timestamp: datetime
    source: str = Field(min_length=2, max_length=80)


def _telegram_configured() -> bool:
    return bool(os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"))


def _deliver(event: dict) -> tuple[str, str | None]:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        return "not_configured", None
    message = (
        f"NATHAN TERMINAL ALERT\n{event['event_type'].replace('_', ' ')}\n"
        f"{event['symbol']} · trade #{event['trade_id']}\n"
        f"Observed price: {event['observed_price']}\n"
        f"Snapshot: {event['market_data_timestamp']}\n"
        "Review the trade manually. No order was placed and the trade was not closed."
    )
    try:
        response = httpx.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": message},
            timeout=8.0,
        )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("ok"):
            return "failed", "Telegram rejected the message."
        return "delivered", None
    except (httpx.HTTPError, ValueError) as exc:
        return "failed", f"Telegram delivery failed: {type(exc).__name__}"


def _send_and_record(conn: sqlite3.Connection, event_id: int) -> dict:
    row = conn.execute("SELECT * FROM monitoring_events WHERE id=?", (event_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Monitoring event not found.")
    event = dict(row)
    status, error = _deliver(event)
    attempts = event["delivery_attempts"] + (1 if status in {"delivered", "failed"} else 0)
    delivered_at = datetime.now(timezone.utc).isoformat() if status == "delivered" else None
    conn.execute(
        "UPDATE monitoring_events SET delivery_status=?,delivery_attempts=?,last_error=?,delivered_at=? WHERE id=?",
        (status, attempts, error, delivered_at, event_id),
    )
    conn.commit()
    updated = dict(conn.execute("SELECT * FROM monitoring_events WHERE id=?", (event_id,)).fetchone())
    return updated


@router.get("/status")
def monitoring_status():
    with _connect() as conn:
        open_count = conn.execute("SELECT COUNT(*) FROM trades WHERE status='OPEN'").fetchone()[0]
        event_count = conn.execute("SELECT COUNT(*) FROM monitoring_events").fetchone()[0]
        failed_count = conn.execute("SELECT COUNT(*) FROM monitoring_events WHERE delivery_status='failed'").fetchone()[0]
        latest = conn.execute("SELECT created_at FROM monitoring_events ORDER BY id DESC LIMIT 1").fetchone()
        return {
            "mode": "snapshot_driven",
            "open_trades": open_count,
            "events": event_count,
            "failed_deliveries": failed_count,
            "telegram_configured": _telegram_configured(),
            "latest_event_at": latest["created_at"] if latest else None,
            "automatic_execution": False,
        }


@router.get("/events")
def list_monitoring_events(limit: int = Query(default=50, ge=1, le=200)):
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM monitoring_events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in rows]


@router.post("/evaluate")
def evaluate_snapshot(snapshot: PriceSnapshot):
    timestamp = snapshot.market_data_timestamp
    if timestamp.tzinfo is None:
        raise HTTPException(status_code=422, detail="Market-data timestamp must include a timezone.")
    age = (datetime.now(timezone.utc) - timestamp.astimezone(timezone.utc)).total_seconds()
    if age < -30 or age > MAX_SNAPSHOT_AGE_SECONDS:
        raise HTTPException(status_code=422, detail="Snapshot is stale or from the future; refresh market data before evaluation.")
    symbol = snapshot.symbol.strip().upper()
    now = datetime.now(timezone.utc).isoformat()
    created = []
    with _connect() as conn:
        trades = conn.execute("SELECT * FROM trades WHERE symbol=? AND status='OPEN' ORDER BY id", (symbol,)).fetchall()
        for row in trades:
            trade = dict(row)
            if trade["direction"] == "LONG":
                event_type = "STOP_LOSS_TOUCHED" if snapshot.current_price <= trade["stop_loss"] else (
                    "TAKE_PROFIT_TOUCHED" if snapshot.current_price >= trade["take_profit"] else None
                )
            else:
                event_type = "STOP_LOSS_TOUCHED" if snapshot.current_price >= trade["stop_loss"] else (
                    "TAKE_PROFIT_TOUCHED" if snapshot.current_price <= trade["take_profit"] else None
                )
            if event_type is None:
                continue
            cursor = conn.execute(
                """INSERT OR IGNORE INTO monitoring_events
                (trade_id,symbol,event_type,observed_price,source,market_data_timestamp,delivery_status,created_at)
                VALUES (?,?,?,?,?,?,?,?)""",
                (trade["id"], symbol, event_type, snapshot.current_price, snapshot.source,
                 timestamp.astimezone(timezone.utc).isoformat(), "pending", now),
            )
            if cursor.rowcount:
                created.append(cursor.lastrowid)
        conn.commit()
        events = [_send_and_record(conn, event_id) for event_id in created]
    return {
        "symbol": symbol,
        "evaluated_open_trades": len(trades),
        "new_events": events,
        "message": "Alerts are informational only. Trades remain open until manually closed in the Trade Desk.",
    }


@router.post("/events/{event_id}/retry")
def retry_delivery(event_id: int):
    with _connect() as conn:
        row = conn.execute("SELECT * FROM monitoring_events WHERE id=?", (event_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Monitoring event not found.")
        if row["delivery_status"] != "failed":
            raise HTTPException(status_code=409, detail="Only failed Telegram deliveries can be retried.")
        if row["delivery_attempts"] >= 5:
            raise HTTPException(status_code=429, detail="Delivery retry limit reached.")
        return _send_and_record(conn, event_id)
