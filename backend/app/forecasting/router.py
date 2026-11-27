from fastapi import APIRouter, HTTPException, Query
from starlette.concurrency import run_in_threadpool

from app.forecasting.kronos import KronosUnavailable, forecast_candles, model_status
from app.market_data.binance import get_binance_candles
from app.market_data.twelve_data import get_twelve_data_candles

router = APIRouter(prefix="/api/v1/forecasts", tags=["forecasts"])


@router.get("/status")
async def status() -> dict:
    return {"engine": "kronos-mini", **model_status()}


@router.get("/{symbol:path}")
async def create_forecast(
    symbol: str,
    interval: str = Query(default="1h"),
    limit: int = Query(default=200, ge=32, le=500),
    pred_len: int = Query(default=24, ge=1, le=48),
    provider: str = Query(default="binance", pattern="^(binance|twelvedata)$"),
) -> dict:
    try:
        if provider == "twelvedata":
            candles = await get_twelve_data_candles(symbol, interval=interval, limit=limit)
        else:
            candles = await get_binance_candles(symbol, interval=interval, limit=limit)
        return await run_in_threadpool(forecast_candles, candles, interval, pred_len)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except KronosUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Forecast request failed: {exc}") from exc
