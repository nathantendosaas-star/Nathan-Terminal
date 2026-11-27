"""Manual-only trade desk and deterministic risk engine."""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone, date
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.trading.risk import calculate_plan

router = APIRouter(prefix="/api/v1/trading", tags=["trade desk"])
DB_PATH = os.getenv("TRADING_DB_PATH", "data/trade_desk.sqlite3")
DEFAULT_SETTINGS = {"account_equity": 10000.0, "account_currency": "USD", "risk_per_trade_pct": 1.0, "maximum_daily_loss_pct": 3.0, "maximum_simultaneous_positions": 3, "minimum_risk_reward": 2.0, "maximum_market_data_age_seconds": 300}


def _connect():
    folder = os.path.dirname(DB_PATH)
    if folder:
        os.makedirs(folder, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("""CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY CHECK(id=1), account_equity REAL NOT NULL, account_currency TEXT NOT NULL, risk_per_trade_pct REAL NOT NULL, maximum_daily_loss_pct REAL NOT NULL, maximum_simultaneous_positions INTEGER NOT NULL, minimum_risk_reward REAL NOT NULL, maximum_market_data_age_seconds INTEGER NOT NULL)""")
    connection.execute("""CREATE TABLE IF NOT EXISTS instruments (symbol TEXT PRIMARY KEY, contract_multiplier REAL NOT NULL, quantity_step REAL NOT NULL, minimum_quantity REAL NOT NULL, quote_currency TEXT NOT NULL, specification_note TEXT NOT NULL)""")
    connection.execute("""CREATE TABLE IF NOT EXISTS trades (id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT NOT NULL, direction TEXT NOT NULL, entry_price REAL NOT NULL, stop_loss REAL NOT NULL, take_profit REAL NOT NULL, quantity REAL NOT NULL, risk_amount REAL NOT NULL, risk_reward REAL NOT NULL, status TEXT NOT NULL, opened_at TEXT NOT NULL, closed_at TEXT, exit_price REAL, realized_pnl REAL)""")
    connection.execute("INSERT OR IGNORE INTO settings (id, account_equity, account_currency, risk_per_trade_pct, maximum_daily_loss_pct, maximum_simultaneous_positions, minimum_risk_reward, maximum_market_data_age_seconds) VALUES (1,?,?,?,?,?,?,?)", tuple(DEFAULT_SETTINGS.values()))
    connection.commit()
    return connection


def _settings(conn):
    return dict(conn.execute("SELECT * FROM settings WHERE id=1").fetchone())


def _instrument(conn, symbol: str):
    row = conn.execute("SELECT * FROM instruments WHERE symbol=?", (symbol.upper(),)).fetchone()
    return dict(row) if row else None


def _exposure(conn):
    rows = conn.execute("SELECT risk_amount FROM trades WHERE status='OPEN'").fetchall()
    return len(rows), sum(float(row["risk_amount"]) for row in rows)


def _daily_pnl(conn):
    today = datetime.now(timezone.utc).date().isoformat()
    row = conn.execute("SELECT COALESCE(SUM(realized_pnl),0) AS pnl FROM trades WHERE status='CLOSED' AND substr(closed_at,1,10)=?", (today,)).fetchone()
    return float(row["pnl"])


class SettingsInput(BaseModel):
    account_equity: float = Field(gt=0, le=1e15)
    account_currency: str = Field(default="USD", min_length=3, max_length=8)
    risk_per_trade_pct: float = Field(gt=0, le=10)
    maximum_daily_loss_pct: float = Field(gt=0, le=100)
    maximum_simultaneous_positions: int = Field(ge=1, le=100)
    minimum_risk_reward: float = Field(gt=0, le=100)
    maximum_market_data_age_seconds: int = Field(default=300, ge=30, le=86400)


class InstrumentInput(BaseModel):
    symbol: str = Field(min_length=1, max_length=30)
    contract_multiplier: float = Field(gt=0, le=1e12)
    quantity_step: float = Field(gt=0, le=1e12)
    minimum_quantity: float = Field(ge=0, le=1e12)
    quote_currency: str = Field(default="USD", min_length=3, max_length=8)
    specification_note: str = Field(min_length=3, max_length=500)


class TradePlan(BaseModel):
    symbol: str = Field(min_length=1, max_length=30)
    direction: Literal["LONG", "SHORT"]
    entry_price: float = Field(gt=0)
    stop_loss: float = Field(gt=0)
    take_profit: float = Field(gt=0)
    quantity: float | None = Field(default=None, gt=0)
    market_price: float | None = Field(default=None, gt=0)
    market_data_timestamp: datetime | None = None


class CloseTrade(BaseModel):
    exit_price: float = Field(gt=0)


def _validate(conn, plan: TradePlan):
    symbol = plan.symbol.strip().upper()
    instrument = _instrument(conn, symbol)
    if instrument is None:
        return {"status": "NEEDS_REVIEW", "reasons": [f"No instrument specification configured for {symbol}. Add verified contract multiplier, quantity step and minimum quantity before sizing or approval."]}
    if plan.market_price is None or plan.market_data_timestamp is None:
        return {"status": "NEEDS_REVIEW", "reasons": ["A current market price and its timestamp are required for freshness validation."]}
    timestamp = plan.market_data_timestamp
    if timestamp.tzinfo is None:
        return {"status": "NEEDS_REVIEW", "reasons": ["Market-data timestamp must include a timezone."]}
    age = (datetime.now(timezone.utc) - timestamp.astimezone(timezone.utc)).total_seconds()
    if age < -30 or age > _settings(conn)["maximum_market_data_age_seconds"]:
        return {"status": "NEEDS_REVIEW", "reasons": [f"Market data is stale or from the future (age {age:.0f}s). Refresh the quote before validation."]}
    if abs(float(plan.market_price) - float(plan.entry_price)) / float(plan.market_price) > 0.02:
        return {"status": "NEEDS_REVIEW", "reasons": ["Entry differs from the supplied current market price by more than 2%; review the intended limit/stop entry."]}
    count, open_risk = _exposure(conn)
    result = calculate_plan(plan.model_dump(), _settings(conn), instrument, count, _daily_pnl(conn), open_risk)
    conflicts = conn.execute("SELECT direction FROM trades WHERE symbol=? AND status='OPEN'", (symbol,)).fetchall()
    if conflicts and any(row["direction"] != plan.direction for row in conflicts):
        result["status"] = "NEEDS_REVIEW"
        result["reasons"].append("An opposite-direction position is already open in this instrument; review portfolio exposure.")
    result["market_data_age_seconds"] = round(age, 2)
    return result


@router.get("/settings")
def get_settings():
    with _connect() as conn:
        return _settings(conn)


@router.put("/settings")
def put_settings(payload: SettingsInput):
    if payload.maximum_daily_loss_pct < payload.risk_per_trade_pct:
        raise HTTPException(status_code=422, detail="Maximum daily loss must be at least the per-trade risk percentage.")
    with _connect() as conn:
        conn.execute("UPDATE settings SET account_equity=?,account_currency=?,risk_per_trade_pct=?,maximum_daily_loss_pct=?,maximum_simultaneous_positions=?,minimum_risk_reward=?,maximum_market_data_age_seconds=? WHERE id=1", tuple(payload.model_dump().values()))
        conn.commit()
        return _settings(conn)


@router.get("/instruments")
def get_instruments():
    with _connect() as conn:
        return [dict(row) for row in conn.execute("SELECT * FROM instruments ORDER BY symbol").fetchall()]


@router.put("/instruments")
def put_instrument(payload: InstrumentInput):
    with _connect() as conn:
        conn.execute("INSERT INTO instruments VALUES (?,?,?,?,?,?) ON CONFLICT(symbol) DO UPDATE SET contract_multiplier=excluded.contract_multiplier,quantity_step=excluded.quantity_step,minimum_quantity=excluded.minimum_quantity,quote_currency=excluded.quote_currency,specification_note=excluded.specification_note", (payload.symbol.strip().upper(), payload.contract_multiplier, payload.quantity_step, payload.minimum_quantity, payload.quote_currency.upper(), payload.specification_note))
        conn.commit()
        return _instrument(conn, payload.symbol)


@router.post("/validate")
def validate_plan(plan: TradePlan):
    with _connect() as conn:
        return _validate(conn, plan)


@router.post("/trades")
def register_trade(plan: TradePlan):
    with _connect() as conn:
        result = _validate(conn, plan)
        if result["status"] != "APPROVED":
            raise HTTPException(status_code=409, detail={"validation": result, "message": "Trade not registered. Resolve all risk checks and explicitly submit again."})
        if plan.quantity is None:
            raise HTTPException(status_code=422, detail="Enter the exact intended quantity before manual registration.")
        cursor = conn.execute("INSERT INTO trades (symbol,direction,entry_price,stop_loss,take_profit,quantity,risk_amount,risk_reward,status,opened_at) VALUES (?,?,?,?,?,?,?,?,?,?)", (plan.symbol.strip().upper(), plan.direction, plan.entry_price, plan.stop_loss, plan.take_profit, plan.quantity, result["planned_risk_amount"], result["risk_reward"], "OPEN", datetime.now(timezone.utc).isoformat()))
        conn.commit()
        return dict(conn.execute("SELECT * FROM trades WHERE id=?", (cursor.lastrowid,)).fetchone())


@router.get("/trades")
def list_trades(status: Literal["OPEN", "CLOSED", "ALL"] = "ALL"):
    with _connect() as conn:
        if status == "ALL":
            rows = conn.execute("SELECT * FROM trades ORDER BY id DESC").fetchall()
        else:
            rows = conn.execute("SELECT * FROM trades WHERE status=? ORDER BY id DESC", (status,)).fetchall()
        return [dict(row) for row in rows]


@router.post("/trades/{trade_id}/close")
def close_trade(trade_id: int, payload: CloseTrade):
    with _connect() as conn:
        row = conn.execute("SELECT * FROM trades WHERE id=?", (trade_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Trade not found.")
        if row["status"] != "OPEN":
            raise HTTPException(status_code=409, detail="Trade is already closed.")
        direction_factor = 1 if row["direction"] == "LONG" else -1
        pnl = (payload.exit_price - row["entry_price"]) * row["quantity"] * direction_factor
        conn.execute("UPDATE trades SET status='CLOSED',closed_at=?,exit_price=?,realized_pnl=? WHERE id=?", (datetime.now(timezone.utc).isoformat(), payload.exit_price, pnl, trade_id))
        conn.commit()
        return dict(conn.execute("SELECT * FROM trades WHERE id=?", (trade_id,)).fetchone())
