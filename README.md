# Nathan Terminal

A personal financial intelligence and trading analysis terminal combining live market data, technical analysis, Kronos-mini forecasting, Gemini-assisted research, and a deterministic risk engine with a manual-only Trade Desk.

## Current capabilities

- [x] React + TypeScript + Vite frontend and FastAPI backend
- [x] Binance crypto and Twelve Data traditional-market OHLCV adapters
- [x] RSI, MACD, EMA/SMA, ATR, swing support/resistance, and market-structure calculations
- [x] Interactive candlestick chart, volume, market selector, and timeframe controls
- [x] Optional Kronos-mini candle forecasting
- [x] Optional Gemini AI research analyst
- [x] Deterministic risk validation and manual trade journal
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

Vite proxies `/api/*` and `/health` to `http://localhost:8000` in development. For a separately hosted API, set `VITE_API_BASE_URL` in the frontend build environment.

## Docker deployment

The repository includes a Docker Compose deployment with a multi-stage frontend image, Nginx reverse proxy, FastAPI container, health checks, and persistent named volumes for the SQLite trade journal and Hugging Face cache.

```bash
cp .env.example .env
# Edit .env and add only the provider keys you need.
docker compose up --build -d
docker compose ps
```

Open `http://localhost:8080` by default. See [DEPLOYMENT.md](DEPLOYMENT.md) for configuration, secrets, backups, HTTPS, health checks, Kronos runtime requirements, and production security considerations.

## Market data

The backend supports two read-only market-data providers:

- Binance public spot klines for crypto; no API key is required.
- Twelve Data time series for supported stocks, forex, ETFs, and other instruments; set `TWELVE_DATA_API_KEY` on the backend.

Select the provider with the `provider` query parameter:

```http
GET /api/v1/markets/BTCUSDT/candles?interval=1h&limit=100&provider=binance
GET /api/v1/markets/AAPL/candles?interval=1h&limit=100&provider=twelvedata
GET /api/v1/markets/EUR%2FUSD/candles?interval=1h&limit=100&provider=twelvedata
```

The API returns UTC OHLCV values and technical analysis. Provider failures are reported explicitly; synthetic fallback prices are not used. The dashboard refreshes through REST polling, not a WebSocket stream. Portfolio metrics and watchlist values remain illustrative placeholders.

## Optional integrations

### Kronos-mini

The forecasting runtime is optional and intentionally excluded from the default Docker image because PyTorch and model weights are substantial. See [backend/README.md](backend/README.md#kronos-mini-forecasting) for the upstream source checkout, runtime dependencies, model configuration, and inference endpoint details.

### Gemini AI Analyst

Set `GEMINI_API_KEY` on the backend to enable the optional research analyst. The key remains server-side. `GEMINI_MODEL` defaults to `gemini-2.5-flash`. Provider quota, latency, and availability are external dependencies.

## Architecture

- **Frontend:** React, TypeScript, Vite, lightweight-charts, Nginx
- **Backend:** Python, FastAPI, Pydantic, httpx
- **Market data:** Binance public REST API and Twelve Data
- **Forecasting:** optional Kronos-mini
- **AI research:** optional Gemini
- **Trade desk:** deterministic risk engine and SQLite journal

## Safety boundaries

This is a research and decision-support tool, not an automated trading bot. The Trade Desk is manual-only: no broker connection, order placement, or automated execution. AI output is never risk approval; all trade plans must pass deterministic checks. Forecasts and AI outputs are estimates, not guarantees or personalized investment advice.
