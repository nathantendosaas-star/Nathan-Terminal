"""Twelve Data adapter for stocks, forex, ETFs, and supported traditional markets.

Requires a Twelve Data API key. Requests are read-only time-series data.
"""
from datetime import datetime, timedelta, timezone
import math
import os
import re
from typing import Any

import httpx
from fastapi import HTTPException

TIME_SERIES_URL = "https://api.twelvedata.com/time_series"
INTERVALS = {
    "1m": ("1min", timedelta(minutes=1)),
    "5m": ("5min", timedelta(minutes=5)),
    "15m": ("15min", timedelta(minutes=15)),
    "30m": ("30min", timedelta(minutes=30)),
    "45m": ("45min", timedelta(minutes=45)),
    "1h": ("1h", timedelta(hours=1)),
    "2h": ("2h", timedelta(hours=2)),
    "4h": ("4h", timedelta(hours=4)),
    "1d": ("1day", timedelta(days=1)),
    "1w": ("1week", timedelta(weeks=1)),
    "1M": ("1month", None),
}


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _candle_end(start: datetime, interval: str, duration: timedelta | None) -> datetime:
    if duration is not None:
        return start + duration
    month = start.month % 12 + 1
    year = start.year + (1 if start.month == 12 else 0)
    return start.replace(year=year, month=month)


def _normalize_values(values: list[dict[str, Any]], interval: str) -> list[dict[str, Any]]:
    provider_interval, duration = INTERVALS[interval]
    candles = []
    for row in values:
        try:
            start = _parse_datetime(str(row["datetime"]))
            numbers = {key: float(row[key]) for key in ("open", "high", "low", "close")}
            volume = float(row.get("volume") or 0)
            if not all(math.isfinite(value) for value in (*numbers.values(), volume)):
                continue
            end = _candle_end(start, interval, duration)
            candles.append({
                "time": start.isoformat(),
                "close_time": end.isoformat(),
                **numbers,
                "volume": volume,
            })
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
    candles.sort(key=lambda candle: candle["time"])
    return candles


async def get_twelve_data_candles(
    symbol: str, interval: str = "1h", limit: int = 100
) -> list[dict[str, Any]]:
    normalized_symbol = symbol.strip().upper()
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9._/-]{0,29}", normalized_symbol):
        raise HTTPException(status_code=422, detail="Invalid symbol format.")
    if interval not in INTERVALS:
        raise HTTPException(status_code=422, detail=f"Unsupported Twelve Data interval: {interval}.")
    if not 1 <= limit <= 500:
        raise HTTPException(status_code=422, detail="Limit must be between 1 and 500.")

    api_key = os.getenv("TWELVE_DATA_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="Twelve Data is not configured. Set TWELVE_DATA_API_KEY on the backend.",
        )

    provider_interval, _ = INTERVALS[interval]
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(12.0, connect=5.0)) as client:
            response = await client.get(
                TIME_SERIES_URL,
                params={
                    "symbol": normalized_symbol,
                    "interval": provider_interval,
                    "outputsize": limit,
                    "timezone": "UTC",
                    "apikey": api_key,
                },
            )
            response.raise_for_status()
            payload = response.json()
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="Twelve Data request timed out.") from exc
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail="Twelve Data returned an HTTP provider error.") from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status_code=502, detail="Unable to retrieve valid data from Twelve Data.") from exc

    if not isinstance(payload, dict):
        raise HTTPException(status_code=502, detail="Twelve Data returned an unexpected response.")
    if payload.get("status") == "error" or payload.get("code"):
        code = payload.get("code")\n        try:\n            code = int(code) if code is not None else None\n        except (TypeError, ValueError):\n            code = None
        if code in (401, 403):
            raise HTTPException(status_code=502, detail="Twelve Data rejected the configured API key.")
        if code == 429:
            raise HTTPException(status_code=503, detail="Twelve Data rate limit reached. Try again later.")
        raise HTTPException(status_code=502, detail="Twelve Data could not provide this symbol or interval.")

    values = payload.get("values")
    if not isinstance(values, list):
        raise HTTPException(status_code=404, detail="No time-series candles were returned for this symbol.")
    candles = _normalize_values(values, interval)
    if not candles:
        raise HTTPException(status_code=502, detail="Twelve Data returned no valid OHLCV candles.")
    return candles
