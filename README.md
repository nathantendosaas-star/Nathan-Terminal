# Nathan Terminal

A personal financial intelligence and trading analysis terminal combining market data, technical analysis, AI-assisted research, and candle forecasting.

## Current status

**Foundation build in progress** on `feat/terminal-foundation`.

- [x] React + TypeScript + Vite frontend scaffold
- [x] Dark terminal dashboard shell with overview, watchlist, and forecast/news placeholders
- [x] FastAPI backend scaffold with health and overview endpoints
- [ ] Verified live market-data adapters
- [ ] Technical indicators and chart integration
- [ ] Kronos-mini forecasting service
- [ ] Gemini research and structured trade-plan generation
- [ ] Deterministic risk validation and manual trade journal
- [ ] News aggregation, monitoring, and Telegram alerts

## Run locally

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

API health check: `http://localhost:8000/health`.

The current dashboard uses clearly labeled illustrative demo values. No live market-data provider, forecasting model, AI provider, or broker integration is connected yet.

## Architecture

- **Frontend:** React, TypeScript, Vite, Recharts (temporary overview visualization)
- **Backend:** Python, FastAPI, Pydantic
- **Planned forecasting:** Kronos-mini
- **Planned AI analysis:** configurable Gemini model
- **Planned market data:** Twelve Data, Binance public REST/WebSocket, Yahoo Finance fallback

## Safety boundaries

This is a research and decision-support tool, not an automated trading bot. It will not place broker orders. Forecasts and AI outputs must be labeled as estimates, risk checks must be deterministic and fail safely when instrument specifications are missing, and the user remains responsible for trade decisions and execution.
