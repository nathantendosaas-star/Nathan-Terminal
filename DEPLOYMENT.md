# Deployment

The supported baseline is a single-host Docker Compose deployment: a static React/Nginx frontend reverse-proxies API requests to FastAPI. The API container is not published directly to the host.

## Requirements

- Docker Engine with the Compose plugin
- A host with enough memory for FastAPI and your chosen workload
- A persistent Docker volume for the manual trade journal
- Provider credentials only for the optional services you enable

## Start

1. Copy `.env.example` to `.env`.
2. Set `APP_PORT` and `FRONTEND_ORIGIN` for your deployment. For a public domain, set `FRONTEND_ORIGIN=https://terminal.example.com`.
3. Add `TWELVE_DATA_API_KEY` and/or `GEMINI_API_KEY` when those integrations are required. Keep secrets only in the host's untracked `.env` file or deployment secret manager.
4. Build and start:

```bash
docker compose up --build -d
docker compose ps
docker compose logs -f api frontend
```

Open `http://localhost:8080` (or your configured `APP_PORT`). The frontend proxies `/api/*` and `/health` to FastAPI, so the browser uses a same-origin API and no public backend port is required.

## Configuration

| Variable | Purpose | Default |
| --- | --- | --- |
| `APP_PORT` | Host port for Nginx | `8080` |
| `FRONTEND_ORIGIN` | Allowed browser origin(s), comma-separated | `http://localhost:8080` |
| `TWELVE_DATA_API_KEY` | Optional traditional-market data | unset |
| `GEMINI_API_KEY` | Optional Gemini analyst | unset |
| `GEMINI_MODEL` | Gemini model identifier | `gemini-2.5-flash` |
| `TRADING_DB_PATH` | SQLite database inside API container | `/data/trade_desk.sqlite3` |
| `HF_HOME` | Hugging Face cache inside API container | `/models/huggingface` |

The Compose file mounts named volumes for trade data and model cache. Back up the `trade_data` volume regularly; container replacement does not remove named volumes, but deleting volumes does. Do not use ephemeral container filesystems for the trade journal.

## Health and operations

- API readiness/liveness endpoint: `GET /health`
- Frontend container health endpoint: `GET /healthz`
- Compose waits for the API health check before starting the frontend.
- Inspect health with `docker compose ps`; inspect logs with `docker compose logs`.
- Apply updates with `docker compose up --build -d`.
- Back up the SQLite volume before upgrades and test restoration periodically.

## Optional Kronos runtime

The default API image intentionally excludes PyTorch and the upstream Kronos source to keep the baseline image smaller. Consequently, the forecast endpoint reports that Kronos is unavailable until its optional runtime is installed. Follow [backend/README.md](backend/README.md#kronos-mini-forecasting) to install the upstream source and `requirements-kronos.txt` into a dedicated forecasting image/worker with suitable CPU or CUDA resources. Do not assume the standard Compose API image can load the model.

## Production security checklist

- Terminate HTTPS at a trusted reverse proxy or managed ingress in front of Nginx.
- Restrict host and container access; do not publish the API port directly.
- Store secrets in a secret manager where available and rotate exposed credentials.
- Configure domain-specific `FRONTEND_ORIGIN`; avoid wildcard CORS origins.
- Restrict access to the application with an authentication layer before exposing it publicly. This MVP does not implement user authentication or authorization.
- Use persistent, backed-up storage for SQLite. SQLite is intended for a single application instance; do not scale API replicas against one shared SQLite file.
- Review resource limits and memory requirements before enabling Kronos inference.
- Confirm provider quotas, data licensing, and service terms for your deployment.

## Important product boundaries

This is research and decision support. The Trade Desk remains manual-only: no broker connection, order submission, or automated execution is included. AI outputs are not risk approvals; the deterministic risk engine remains authoritative. No stop execution or loss limit is guaranteed.
