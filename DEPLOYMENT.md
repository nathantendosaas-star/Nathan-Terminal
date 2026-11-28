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

## Single-owner password protection

Password protection is initialized from the app itself; no terminal, laptop, password-hash command, or manually generated signing secret is required.

1. Deploy the backend with a persistent database path. The default auth database shares the trade-journal SQLite file; in Docker Compose it is mounted at `/data/trade_desk.sqlite3`.
2. Open the HTTPS frontend on your phone. On first visit, the app displays a **Create your password** screen.
3. Enter and confirm a unique password of at least 12 characters. The browser sends it over HTTPS to the backend's one-time setup endpoint. The backend hashes it with scrypt and stores only the hash.
4. The backend generates and stores its own random signing secret in the same persistent database. You do not need to create or configure `AUTH_SECRET_KEY`.

The setup endpoint is one-time only. Later visits show the normal password login. Keep the database on persistent storage and restrict access to the backend/database; losing the database means losing the configured password and signing secret. Existing deployments may continue using legacy `APP_PASSWORD_HASH` and `AUTH_SECRET_KEY` environment variables, but new installs should use in-app setup.

Sessions remain signed bearer tokens with a 12-hour lifetime and are stored in tab-scoped `sessionStorage`. Use HTTPS for every public deployment. OAuth, multi-user accounts, password reset, and account recovery remain out of scope.

## Gemini model selection

Set `GEMINI_API_KEY` only in the backend's Render environment. The default model is `gemini-3.8-flash`; the AI Analyst workspace lets you switch to `gemini-3.6-flash`. The selected model is saved in the backend's persistent SQLite settings and is used for subsequent analysis requests. Never place the Gemini API key in Vercel frontend variables.
