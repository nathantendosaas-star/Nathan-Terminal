# Nathan Terminal

A personal financial intelligence and trading analysis terminal combining market data, technical analysis, AI-assisted research, and candle forecasting.

## Current status

**Market-data foundation in progress** on `feat/binance-market-data`.

- [x] React + TypeScript + Vite frontend scaffold
- [x] Dark terminal dashboard shell with overview, watchlist, and forecast/news placeholders
- [x] FastAPI backend scaffold with health and overview endpoints
- [x] Binance public REST adapter for spot OHLCV candles
- [x] BTC/USDT chart connected to Binance REST with 60-second refresh
- [ ] Twelve Data adapter for traditional markets
- [x] RSI, MACD, EMA/SMA, ATR, swing support/resistance, and market-structure calculations
- [ ] Dedicated candlestick chart
- [ ] Kronos-mini forecasting service
- [ ] Gemini research and structured trade-plan generation
- [ ] Deterministic risk validation and manual trade journal
- [ ] News aggregation, monitoring, and Telegram alerts

## Run locally

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Optional frontend environment file: copy `frontend/.env.example` to `frontend/.env.local` and set `VITE_API_BASE_URL` if the API is not running at `http://localhost:8000`.

## Market data API

The backend calls Binance's public spot klines endpoint; no API key or trading permission is required.

```http
GET /api/v1/markets/BTCUSDT/candles?interval=1h&limit=100
```

Supported intervals include `1m`, `5m`, `15m`, `1h`, `4h`, `1d`, and other Binance spot intervals. The API validates symbols, intervals, and limits (1–500), returns UTC timestamps and OHLCV values, and reports provider failures rather than inventing prices.

The chart refreshes the latest 100 hourly candles every 60 seconds. This is REST polling, not a WebSocket stream. If the API is unavailable, the chart falls back to clearly labeled illustrative demo data. Other dashboard metrics and watchlist values remain demo placeholders.

## Architecture

- **Frontend:** React, TypeScript, Vite, Recharts
- **Backend:** Python, FastAPI, Pydantic, httpx
- **Live crypto market data:** Binance public REST API
- **Planned traditional-market data:** Twelve Data
- **Planned forecasting:** Kronos-mini
- **Planned AI analysis:** configurable Gemini model

## Safety boundaries

This is a research and decision-support tool, not an automated trading bot. It will not place broker orders. Forecasts and AI outputs must be labeled as estimates, risk checks must be deterministic and fail safely when instrument specifications are missing, and the user remains responsible for trade decisions and execution.
