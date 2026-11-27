# Backend

FastAPI service for market data adapters, forecasting orchestration, AI analysis, deterministic risk checks, and manual trade journaling.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## Endpoints

- `GET /health` — API health and configured market-data provider.
- `GET /api/v1/overview` — current capability status.
- `GET /api/v1/markets/{symbol}/candles?interval=1h&limit=100` — Binance public spot OHLCV candles.

The Binance adapter requires no API key. It validates symbol syntax, supported intervals, and a 1–500 candle limit; normalizes timestamps to UTC; and returns explicit provider errors for timeouts, invalid markets, or upstream failures. It does not access account data or place orders.

The frontend's local default API origin is `http://localhost:8000`. Configure its `VITE_API_BASE_URL` environment variable when the API is hosted elsewhere.
