"""Binance public spot-market candle adapter.

Only public market data is requested; no API key or trading permission is needed.
"""
from datetime import datetime, timezone
import re
from typing import Any

import httpx
from fastapi import HTTPException

BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"
ALLOWED_INTERVALS = {
    "1m", "3m", "5m", "15m", "30m",
    "1h", "2h", "4h", "6h", "8h", "12h",
    "1d", "3d", "1w", "1M",
}


def _utc_iso(milliseconds: int) -> str:
    return datetime.fromtimestamp(milliseconds / 1000, tz=timezone.utc).isoformat()


async def get_binance_candles(symbol: str, interval: str = "1h", limit: int = 100) -> list[dict[str, Any]]:
    normalized_symbol = symbol.upper().replace("/", "").replace("-", "")
    if not re.fullmatch(r"[A-Z0-9]{5,20}", normalized_symbol):
        raise HTTPException(status_code=422, detail="Invalid symbol. Use a pair such as BTCUSDT.")
    if interval not in ALLOWED_INTERVALS:
        raise HTTPException(status_code=422, detail=f"Unsupported interval: {interval}.")
    if not 1 <= limit <= 500:
        raise HTTPException(status_code=422, detail="Limit must be between 1 and 500.")

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0)) as client:
            response = await client.get(
                BINANCE_KLINES_URL,
                params={"symbol": normalized_symbol, "interval": interval, "limit": limit},
            )
            response.raise_for_status()
            payload = response.json()
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="Binance market-data request timed out.") from exc
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 400:
            raise HTTPException(status_code=404, detail="Binance does not recognize this symbol or interval.") from exc
        raise HTTPException(status_code=502, detail="Binance market-data provider returned an error.") from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status_code=502, detail="Unable to retrieve valid data from Binance.") from exc

    if not isinstance(payload, list):
        raise HTTPException(status_code=502, detail="Binance returned an unexpected candle payload.")

    candles = []
    for row in payload:
        if not isinstance(row, list) or len(row) < 7:
            continue
        try:
            candles.append({
                "time": _utc_iso(int(row[0])),
                "close_time": _utc_iso(int(row[6])),
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "volume": float(row[5]),
            })
        except (TypeError, ValueError, OverflowError):
            continue

    if not candles:
        raise HTTPException(status_code=404, detail="No candles were returned for this market.")
    return candles
