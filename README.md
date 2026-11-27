# Nathan Terminal

A personal financial intelligence and trading analysis terminal combining market data, technical analysis, AI-assisted research, and candle forecasting.

## Current status

**Market-data foundation:** Binance crypto candles and Twelve Data traditional-market adapter.

- [x] React + TypeScript + Vite frontend scaffold
- [x] Dark terminal dashboard shell with overview, watchlist, and forecast/news placeholders
- [x] FastAPI backend scaffold with health and overview endpoints
- [x] Binance public REST adapter for spot OHLCV candles
- [x] BTC/USDT chart connected to Binance REST with 60-second refresh
- [x] Twelve Data adapter for traditional markets (API key required)
- [x] RSI, MACD, EMA/SMA, ATR, swing support/resistance, and market-structure calculations
- [x] Unit tests for technical indicator edge cases
- [x] Interactive OHLC candlestick chart with volume, market selector, and timeframe controls
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

The backend supports two read-only market-data providers:

- Binance public spot klines for crypto; no API key is required.
- Twelve Data time series for supported stocks, forex, ETFs, and other instruments; set `TWELVE_DATA_API_KEY` on the backend.

Select the provider with the `provider` query parameter:

```http
GET /api/v1/markets/BTCUSDT/candles?interval=1h&limit=100&provider=binance
GET /api/v1/markets/AAPL/candles?interval=1h&limit=100&provider=twelvedata
GET /api/v1/markets/EUR%2FUSD/candles?interval=1h&limit=100&provider=twelvedata
```

Supported intervals include `1m`, `5m`, `15m`, `1h`, `4h`, `1d`, and other Binance spot intervals. The API validates symbols, intervals, and limits (1–500), returns UTC timestamps and OHLCV values, and reports provider failures rather than inventing prices.

The Twelve Data adapter normalizes returned candles to chronological UTC OHLCV records. Its supported intervals are 1m, 5m, 15m, 30m, 45m, 1h, 2h, 4h, 1d, 1w, and 1M. API-key absence, provider errors, and rate limits are reported explicitly; no fallback prices are fabricated.

The chart supports BTC/USDT, ETH/USDT, and SOL/USDT through Binance, plus AAPL, NVDA, and EUR/USD through Twelve Data. Choose a market and interval in the chart controls. It renders OHLC candles, volume bars, EMA 20/50 overlays, and available confirmed support/resistance levels from the technical-analysis response. Data refreshes through REST polling every 60 seconds; this is not a WebSocket stream. If a provider request fails, the chart displays the error instead of inventing fallback prices. Portfolio metrics and watchlist values remain illustrative placeholders.

## Architecture

- **Frontend:** React, TypeScript, Vite, lightweight-charts
- **Backend:** Python, FastAPI, Pydantic, httpx
- **Live crypto market data:** Binance public REST API
- **Traditional-market data:** Twelve Data
- **Planned forecasting:** Kronos-mini
- **Planned AI analysis:** configurable Gemini model

## Safety boundaries

This is a research and decision-support tool, not an automated trading bot. It will not place broker orders. Forecasts and AI outputs must be labeled as estimates, risk checks must be deterministic and fail safely when instrument specifications are missing, and the user remains responsible for trade decisions and execution.
