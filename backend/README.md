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

## Gemini AI Analyst

The optional AI Analyst uses Google's Gemini API from the backend. The API key is never sent to the browser.

1. Create a Gemini API key in Google AI Studio.
2. Set `GEMINI_API_KEY` in the backend environment (see `.env.gemini.example`). Optionally set `GEMINI_MODEL`; the default is `gemini-2.5-flash`.
3. Restart the backend.

- `GET /api/v1/analysis/status` — reports whether Gemini is configured and the selected model.
- `POST /api/v1/analysis` — accepts `symbol`, `interval`, `provider` and an optional `question`; fetches up to 200 real candles, calculates technical indicators, and asks Gemini for a structured research read.
- The analyst covers trend, momentum, volatility, levels, bull/base/bear scenarios, invalidation and missing context. It does not generate trade orders or personalized recommendations.
- Gemini is an external paid/quota-limited service depending on the user's Google AI plan. Requests may fail when the key, quota, or provider is unavailable.


## Risk Engine and Manual Trade Desk

The trade desk is deliberately manual-only. It does not connect to a broker, submit orders, or execute trades.

### Configure before using position sizing

1. Set account equity, account currency, risk per trade, maximum daily loss, maximum simultaneous open positions, minimum risk/reward, and market-data freshness threshold with `PUT /api/v1/trading/settings`.
2. Register verified instrument specifications with `PUT /api/v1/trading/instruments`: contract multiplier, quantity step, minimum quantity, quote currency, and a note describing the source/contract. No instrument multiplier or broker constraint is assumed by the application.
3. Validate a plan using `POST /api/v1/trading/validate`. Include symbol, LONG/SHORT, entry, stop-loss, take-profit, exact intended quantity (optional for sizing preview), current market price, and timezone-aware market-data timestamp.
4. Only an `APPROVED` plan with an explicit quantity can be manually registered using `POST /api/v1/trading/trades`. Validation never registers or modifies a plan.
5. Review `GET /api/v1/trading/trades`; close a journal entry with `POST /api/v1/trading/trades/{trade_id}/close` and an exit price.

### Risk rules

- Position sizing uses configured account equity, risk percentage, contract multiplier, quantity step, and minimum quantity; suggested quantities are rounded down.
- Validates direction-specific stop/target placement, risk/reward, per-trade risk budget, daily loss exposure, maximum simultaneous positions, market quote freshness, and conflicting opposite-direction positions.
- Outcomes are `APPROVED`, `REJECTED`, or `NEEDS_REVIEW`. Missing instrument specifications or quote context require review; hard rule violations reject the plan.
- The local SQLite journal is stored at `data/trade_desk.sqlite3` by default. Set `TRADING_DB_PATH` to a persistent mounted path in deployment; ephemeral hosting filesystems may lose journal data.
- P&L journal calculations are gross price-difference calculations and do not include commissions, spread, funding, swaps, slippage, taxes, or currency conversion. Validate contract specs and quote/account currency compatibility yourself.
- This tool is a decision-support calculator, not financial advice. It does not guarantee fills, stops, or realized loss limits.


## Gemini Trade Thesis Reassessment

The Thesis Review workspace compares an open manual trade against its immutable original thesis and original Gemini analysis. On each user-requested reassessment the backend fetches up to 200 real candles from Binance or Twelve Data, recalculates technical indicators, and retrieves relevant Google News RSS headlines when enabled. An optional Kronos forecast context can be supplied by API clients; it is treated as uncertain evidence, not ground truth.

- `POST /api/v1/thesis/trades/{trade_id}/reassess` — reassess an open trade. The first request must include `original_thesis` and `original_analysis`; both are saved as the immutable baseline. Subsequent requests reuse that baseline.
- `GET /api/v1/thesis/trades/{trade_id}/history` — retrieve the baseline, reassessment history, evidence snapshots, and deduplicated alerts.
- Gemini must return structured JSON with status `VALID`, `WEAKENED`, `INVALIDATED`, or `NEEDS_REVIEW`, plus assessment, changes, supporting/contradicting/missing evidence, and confidence.
- Candle timestamps are checked for freshness using `THESIS_MAX_CANDLE_AGE_SECONDS` (default 7200 seconds). Stale or malformed candle evidence is rejected before Gemini is called. If the requested news feed is unavailable, the result is downgraded to `NEEDS_REVIEW`.
- `WEAKENED` and `INVALIDATED` create in-app monitoring events and use the existing optional Telegram delivery pipeline. Alerts are deduplicated per trade and status.
- Reassessment is on demand, not a background watcher. It never modifies a trade plan, closes a trade, changes risk approval, or submits broker orders. A Gemini status is not a risk-engine outcome.
- Gemini output and news are untrusted research context. Verify cited sources independently; absence of headlines is not evidence that no event exists.
