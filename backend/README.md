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


## Kronos-mini forecasting

Kronos is an optional, lazily loaded forecasting runtime. The first forecast request loads the upstream model/tokenizer into memory; subsequent requests reuse the process-local predictor. CPU is selected by default, with CUDA used when available. Keep the model service on a worker with sufficient RAM; model weights are downloaded from Hugging Face on first load and cached by the Hugging Face client.

Install the upstream source and runtime dependencies from the `backend` directory:

```bash
git clone --depth 1 https://github.com/shiyu-coder/Kronos.git vendor/Kronos
pip install -r requirements-kronos.txt
```

The default source path is `backend/vendor/Kronos`. Set `KRONOS_SOURCE_PATH` if you clone it elsewhere. The default model pair is `NeoQuasar/Kronos-mini` and `NeoQuasar/Kronos-Tokenizer-2k`. The model can be configured with `KRONOS_MODEL_ID`, `KRONOS_TOKENIZER_ID`, `KRONOS_MAX_CONTEXT`, and `KRONOS_PRED_LEN`.

- `GET /api/v1/forecasts/status` — model load status and last load error.
- `GET /api/v1/forecasts/{symbol}?provider=binance&interval=1h&limit=200&pred_len=24` — fetches real OHLCV data and returns observed candles separately from model-generated forecast candles.
- Supported provider values: `binance` and `twelvedata`; supported forecast intervals: 1m, 5m, 15m, 30m, 1h, 2h, 4h, 1d, 1w, and 1M.
- Minimum history: 32 candles. Forecast horizon: 1–48 candles. The API caps model context at the configured context length.
- The response includes inference duration and process peak resident memory where the platform exposes it. These are runtime observations, not benchmark guarantees.

The model is loaded only on demand. If the upstream source or model weights are unavailable, the API returns an explicit 503 error; it never substitutes synthetic forecasts. Kronos forecasts are probabilistic estimates for research, not trading signals or investment advice.