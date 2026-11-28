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
- [x] Google News RSS aggregation and search
- [x] Snapshot-driven trade monitoring with persisted, deduplicated stop-loss / take-profit alerts
- [x] Optional Telegram alert delivery with retry tracking
- [x] Gemini trade-thesis reassessment with evidence history and deduplicated alerts

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

## News and monitoring

- `GET /api/v1/news?q=bitcoin&limit=20` retrieves headlines through Google News RSS. Provider availability and source links remain external dependencies.
- `GET /api/v1/monitoring/status` and `GET /api/v1/monitoring/events` expose monitoring status and persisted events.
- `POST /api/v1/monitoring/evaluate` evaluates a timestamped market-price snapshot against open manual trades. Snapshots older than `MONITORING_MAX_SNAPSHOT_AGE_SECONDS` are rejected.
- The Monitoring workspace checks the latest fetched candle only when the user requests an evaluation. This is snapshot-driven, not a continuously running background price watcher.
- Stop-loss / take-profit events are deduplicated per trade and event type. Telegram delivery is optional: configure `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`. Failed or not-configured deliveries can be retried, with a five-attempt cap.
- Monitoring never closes trades, edits plans, or submits broker orders. A touched level is an alert for manual review, not proof of execution or a guaranteed fill.

## Thesis reassessment

The Thesis Review workspace reassesses open trade theses against fresh provider candles, technical indicators, and available Google News headlines. It preserves the original thesis and analysis, records each assessment, and alerts on weakened or invalidated theses. See [backend/README.md](backend/README.md#gemini-trade-thesis-reassessment) for API details and evidence freshness rules. AI review never changes risk approval or executes trades.

## Architecture

- **Frontend:** React, TypeScript, Vite, lightweight-charts, Nginx
- **Backend:** Python, FastAPI, Pydantic, httpx
- **Market data:** Binance public REST API and Twelve Data
- **Forecasting:** optional Kronos-mini
- **AI research:** optional Gemini
- **Trade desk:** deterministic risk engine and SQLite journal

## Safety boundaries

This is a research and decision-support tool, not an automated trading bot. The Trade Desk is manual-only: no broker connection, order placement, or automated execution. AI output is never risk approval; all trade plans must pass deterministic checks. Forecasts and AI outputs are estimates, not guarantees or personalized investment advice.


## Session lifecycle

Market-data polling is session-scoped. The terminal starts with polling paused; use **Start 8h session** to activate the six-symbol subscription set (BTCUSDT, ETHUSDT, SOLUSDT, NVDA, AAPL, GOOGL). The selected candle timeframe is fixed for the session. The browser refreshes the selected symbol every 60 seconds and checks session expiry every 15 seconds. Stopping or expiry tears down the polling interval; no WebSocket or provider stream is left running in the backend.

- `GET /api/v1/sessions/current` — current active session or no active session.
- `POST /api/v1/sessions/start` — starts one session with an 8-hour hard maximum; only one active session is allowed.
- `POST /api/v1/sessions/{session_id}/stop` — stops an active session; repeated stop requests are safe.
- `GET /api/v1/sessions/history` — last 50 persisted sessions.
- Session records live in SQLite at `SESSION_DB_PATH` (default `data/sessions.sqlite3` locally; persistent `/data/market_sessions.sqlite3` volume path in Compose). Existing trade journal, monitoring events, thesis records and analysis history are not cleared when a session ends.
- Session expiry is enforced on session API access. The running browser polls status every 15 seconds and clears market polling when expiry is observed. If the browser is closed, it has no active client subscription to clean up.
- Sessions describe the app's REST polling subscriptions; they do not create a continuous server-side WebSocket feed. The terminal is still manual research only and never places broker orders.
