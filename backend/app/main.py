from datetime import datetime, timezone
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.market_data.binance import get_binance_candles
from app.market_data.technical import calculate_technical_analysis

app = FastAPI(title="Nathan Terminal API", version="0.2.0", description="Personal market intelligence and decision-support API.")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


class ServiceStatus(BaseModel):
    status: str
    service: str
    version: str
    timestamp: datetime
    market_data: str


@app.get("/health", response_model=ServiceStatus)
async def health() -> ServiceStatus:
    return ServiceStatus(status="ok", service="nathan-terminal-api", version=app.version, timestamp=datetime.now(timezone.utc), market_data="binance_public_api")


@app.get("/api/v1/overview")
async def overview() -> dict[str, str]:
    return {"mode": "research_only", "market_data": "binance_public_api", "forecast_model": "not_configured", "message": "Live crypto candles are available through the markets endpoint. Other dashboard metrics may still be illustrative."}


@app.get("/api/v1/markets/{symbol}/candles")
async def market_candles(
    symbol: str,
    interval: str = Query(default="1h"),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict:
    candles = await get_binance_candles(symbol, interval=interval, limit=limit)
    return {
        "symbol": symbol.upper().replace("/", "").replace("-", ""),
        "interval": interval,
        "source": "binance_spot",
        "is_live": True,
        "count": len(candles),
        "candles": candles,
        "technical_analysis": calculate_technical_analysis(candles),
    }
