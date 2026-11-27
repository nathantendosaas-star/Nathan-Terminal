# Backend

FastAPI service for market data adapters, forecasting orchestration, AI analysis, deterministic risk checks, and manual trade journaling.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## Tests

From the `backend` directory, run the standard-library unit tests with:

```bash
python -m unittest discover -s tests -v
```

## Endpoints

- `GET /health` — API health and configured market-data provider.
- `GET /api/v1/overview` — current capability status.
- `GET /api/v1/markets/{symbol}/candles?interval=1h&limit=100` — Binance public spot OHLCV candles.

The Binance adapter requires no API key. It validates symbol syntax, supported intervals, and a 1–500 candle limit; normalizes timestamps to UTC; and returns explicit provider errors for timeouts, invalid markets, or upstream failures. It does not access account data or place orders.

The candle response also includes a deterministic technical-analysis snapshot: Wilder RSI(14), MACD(12, 26, 9), EMA/SMA(20, 50), ATR(14), latest confirmed two-sided swing support/resistance, and a simple higher-high/higher-low or lower-high/lower-low structure label. Indicators return null when history is insufficient. Swing levels use a two-candle confirmation radius and can appear with a delay. These are descriptive calculations, not trading signals or forecasts.

The frontend's local default API origin is `http://localhost:8000`. Configure its `VITE_API_BASE_URL` environment variable when the API is hosted elsewhere.
