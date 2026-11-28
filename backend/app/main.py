from datetime import datetime, timezone
import os
from typing import Literal

from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.market_data.binance import get_binance_candles
from app.market_data.twelve_data import get_twelve_data_candles
from app.market_data.technical import calculate_technical_analysis
from app.forecasting.router import router as forecasting_router
from app.analysis.router import router as analysis_router
from app.trading.router import router as trading_router
from app.monitoring.router import router as monitoring_router
from app.news.router import router as news_router
from app.thesis.router import router as thesis_router
from app.sessions.router import router as sessions_router
from app.auth.router import router as auth_router, token_is_valid, auth_is_configured

app = FastAPI(title="Nathan Terminal API", version="0.4.0", description="Personal market intelligence and decision-support API.")
app.include_router(forecasting_router)
app.include_router(analysis_router)
app.include_router(trading_router)
app.include_router(monitoring_router)
app.include_router(news_router)
app.include_router(thesis_router)
app.include_router(sessions_router)
app.include_router(auth_router)

# Comma-separated origins support separate frontend domains in production.
# Same-origin deployments through the included Nginx proxy do not need CORS.
frontend_origins = [
    origin.strip().rstrip("/")
    for origin in os.getenv("FRONTEND_ORIGIN", "http://localhost:5173").split(",")
    if origin.strip()
]
@app.middleware("http")
async def password_guard(request: Request, call_next):
    path = request.url.path
    if path.startswith("/api/") and path not in {"/api/v1/auth/status", "/api/v1/auth/login"} and request.method != "OPTIONS":
        if auth_is_configured():
            authorization = request.headers.get("authorization", "")
            token = authorization.removeprefix("Bearer ").strip() if authorization.startswith("Bearer ") else ""
            if not token or not token_is_valid(token):
                return JSONResponse(status_code=401, content={"detail": "Authentication required. Unlock your terminal and try again."})
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=frontend_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


class ServiceStatus(BaseModel):
    status: str
    service: str
    version: str
    timestamp: datetime
    market_data: str


@app.get("/health", response_model=ServiceStatus)
async def health() -> ServiceStatus:
    return ServiceStatus(status="ok", service="nathan-terminal-api", version=app.version, timestamp=datetime.now(timezone.utc), market_data="binance_and_twelve_data")


@app.get("/api/v1/overview")
async def overview() -> dict[str, str]:
    return {
        "mode": "research_only",
        "market_data": "binance_and_twelve_data",
        "forecast_model": "kronos_mini_optional",
        "ai_analyst": "gemini_optional",
        "trade_desk": "manual_only",
        "session_max_duration_hours": "8",
        "message": "Market data, Kronos-mini forecasts, Gemini analysis, and a manual-only trade desk are available; no broker execution is enabled.",
    }


@app.get("/api/v1/markets/{symbol:path}/candles")
async def market_candles(
    symbol: str,
    interval: str = Query(default="1h"),
    limit: int = Query(default=100, ge=1, le=500),
    provider: Literal["binance", "twelvedata"] = Query(default="binance"),
) -> dict:
    if provider == "twelvedata":
        candles = await get_twelve_data_candles(symbol, interval=interval, limit=limit)
        source = "twelve_data"
        normalized_symbol = symbol.strip().upper()
    else:
        candles = await get_binance_candles(symbol, interval=interval, limit=limit)
        source = "binance_spot"
        normalized_symbol = symbol.upper().replace("/", "").replace("-", "")

    return {
        "symbol": normalized_symbol,
        "interval": interval,
        "source": source,
        "is_live": True,
        "count": len(candles),
        "candles": candles,
        "technical_analysis": calculate_technical_analysis(candles),
    }
