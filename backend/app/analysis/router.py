"""Gemini-powered market research endpoint. The API key remains server-side."""
import os
from typing import Literal

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.market_data.binance import get_binance_candles
from app.market_data.twelve_data import get_twelve_data_candles
from app.market_data.technical import calculate_technical_analysis
from app.auth.router import get_setting, set_setting

router = APIRouter(prefix="/api/v1/analysis", tags=["AI analysis"])
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
GEMINI_MODELS = ("gemini-3.8-flash", "gemini-3.6-flash")
DEFAULT_GEMINI_MODEL = "gemini-3.8-flash"


class ModelSelection(BaseModel):
    model: Literal["gemini-3.8-flash", "gemini-3.6-flash"]


class AnalysisRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=30)
    interval: str = Field(default="1h", min_length=2, max_length=4)
    provider: Literal["binance", "twelvedata"] = "binance"
    question: str = Field(default="Give me a balanced market read: trend, momentum, volatility, key levels, scenarios and what would invalidate each scenario.", max_length=1200)


def build_analysis_prompt(symbol: str, interval: str, candles: list[dict], technical: dict, question: str) -> str:
    recent = candles[-30:]
    compact = [{key: candle[key] for key in ("time", "open", "high", "low", "close", "volume")} for candle in recent]
    return (
        "You are a careful financial research analyst. Analyze only the supplied data. "
        "Do not invent news, fundamentals, prices, or certainty. Distinguish observations from hypotheses. "
        "Include: executive summary; trend and market structure; momentum; volatility; support/resistance; "
        "bull/base/bear scenarios with explicit invalidation; missing context and risks. "
        "Use concise headings and cite numeric values from the input. Never issue personalized investment advice, "
        "guaranteed predictions, position sizing, or direct buy/sell instructions. State that this is research, not advice.\n\n"
        f"Instrument: {symbol}\nTimeframe: {interval}\nCandles are chronological UTC OHLCV; latest 30 only: {compact}\n"
        f"Calculated indicators: {technical}\nUser question: {question}"
    )


@router.get("/status")
async def analysis_status() -> dict:
    return {"provider": "Google Gemini API", "configured": bool(os.getenv("GEMINI_API_KEY", "").strip()), "model": get_setting("gemini_model", os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)), "models": list(GEMINI_MODELS)}


@router.put("/model")
async def select_gemini_model(selection: ModelSelection) -> dict:
    if not os.getenv("GEMINI_API_KEY", "").strip():
        raise HTTPException(status_code=503, detail="Gemini is not configured. Set GEMINI_API_KEY on the backend.")
    set_setting("gemini_model", selection.model)
    return {"model": selection.model, "saved": True}


@router.post("")
async def analyze_market(request: AnalysisRequest) -> dict:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(status_code=503, detail="Gemini is not configured. Set GEMINI_API_KEY on the backend.")
    if request.provider == "twelvedata":
        candles = await get_twelve_data_candles(request.symbol, interval=request.interval, limit=200)
        source = "twelve_data"
        symbol = request.symbol.strip().upper()
    else:
        candles = await get_binance_candles(request.symbol, interval=request.interval, limit=200)
        source = "binance_spot"
        symbol = request.symbol.upper().replace("/", "").replace("-", "")
    technical = calculate_technical_analysis(candles)
    prompt = build_analysis_prompt(symbol, request.interval, candles, technical, request.question.strip())
    model = get_setting("gemini_model", os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)).strip()
    if model not in GEMINI_MODELS:
        model = DEFAULT_GEMINI_MODEL
    url = f"{GEMINI_BASE_URL}/{model}:generateContent"
    payload = {"contents": [{"role": "user", "parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.25, "maxOutputTokens": 1800}}
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(45.0, connect=8.0)) as client:
            response = await client.post(url, headers={"x-goog-api-key": api_key}, json=payload)
            response.raise_for_status()
            data = response.json()
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="Gemini analysis timed out. Try again.") from exc
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in (401, 403):
            raise HTTPException(status_code=502, detail="Gemini rejected the configured API key.") from exc
        if exc.response.status_code == 429:
            raise HTTPException(status_code=503, detail="Gemini rate limit or quota reached. Try again later.") from exc
        raise HTTPException(status_code=502, detail="Gemini returned an upstream error.") from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status_code=502, detail="Unable to retrieve a valid Gemini response.") from exc

    candidates = data.get("candidates") or []
    parts = (candidates[0].get("content") or {}).get("parts") or [] if candidates else []
    answer = "\n".join(part.get("text", "") for part in parts if isinstance(part, dict)).strip()
    if not answer:
        raise HTTPException(status_code=502, detail="Gemini returned no analysis text.")
    return {"symbol": symbol, "interval": request.interval, "source": source, "model": model, "generated_at": datetime.now(timezone.utc).isoformat(), "candles_analyzed": len(candles), "technical_analysis": technical, "analysis": answer, "disclaimer": "AI-generated market research can be wrong or incomplete. Not investment advice or a trading signal."}
