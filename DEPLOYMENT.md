# Deployment

The supported baseline is a single-host Docker Compose deployment: a static React/Nginx frontend reverse-proxies API requests to FastAPI. The API container is not published directly to the host.

## Requirements

- Docker Engine with the Compose plugin
- A host with enough memory for FastAPI and your chosen workload
- A Supabase PostgreSQL project (PostgreSQL 17 recommended)
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

## Supabase PostgreSQL configuration

1. In the Supabase dashboard, open project **Nathan-Terminal** and confirm the project is active.
2. Open **SQL Editor** and run the contents of `backend/migrations/001_initial_postgresql.sql`. This creates the private `app` schema and all tables used by the API.
3. Open **Connect** and copy the **Session Pooler** connection string. Use it as the backend's `DATABASE_URL` secret. Do not put it in Vercel, source control, or any `VITE_*` variable.
4. Set `DATABASE_SCHEMA=app` in the backend environment. The application uses direct server-side PostgreSQL access; the Supabase service-role key and browser Data API are not needed.
5. Redeploy the backend after adding the database variables. The API health check should pass only after the database is reachable and startup initialization succeeds.

For Docker Compose, put `DATABASE_URL` in the untracked `.env` file before starting. The old `AUTH_DB_PATH`, `TRADING_DB_PATH`, and `SESSION_DB_PATH` variables and SQLite persistent volume are no longer used.

## Single-owner password protection

Password protection is initialized from the app itself; no terminal, laptop, password-hash command, or manually generated signing secret is required.

1. Deploy the backend with `DATABASE_URL` set to the Supabase Session Pooler connection string and `DATABASE_SCHEMA=app`.
2. Open the HTTPS frontend on your phone. On first visit, the app displays a **Create your password** screen.
3. Enter and confirm a unique password of at least 12 characters. The browser sends it over HTTPS to the backend's one-time setup endpoint. The backend hashes it with scrypt and stores only the hash.
4. The backend generates and stores its own random signing secret in the PostgreSQL `app.app_settings` table. You do not need to create or configure `AUTH_SECRET_KEY`.

The setup endpoint is one-time only. Later visits show the normal password login. Keep the Supabase database active and backed up; losing the database means losing the configured password and signing secret. Existing deployments may continue using legacy `APP_PASSWORD_HASH` and `AUTH_SECRET_KEY` environment variables, but new installs should use in-app setup.

Sessions remain signed bearer tokens with a 12-hour lifetime and are stored in tab-scoped `sessionStorage`. Use HTTPS for every public deployment. OAuth, multi-user accounts, password reset, and account recovery remain out of scope.

## Gemini model selection

Set `GEMINI_API_KEY` only in the backend's Render environment. The default model is `gemini-3.8-flash`; the AI Analyst workspace lets you switch to `gemini-3.6-flash`. The selected model is saved in the backend's persistent PostgreSQL settings and is used for subsequent analysis requests. Never place the Gemini API key in Vercel frontend variables.


## PWA phone notifications

The frontend is installable as a PWA and uses browser Web Push. Serve it over HTTPS (localhost is supported for development). Set VAPID_SUBJECT to a valid mailto: or HTTPS contact identity. The backend creates a VAPID keypair automatically and stores the private key in Supabase PostgreSQL; do not copy it into Vercel or the frontend.

On Android, open the HTTPS terminal in Chrome, choose Install app or Add to Home screen, launch the installed app, open Monitoring, and choose Enable phone notifications. On iOS, add the app to the Home Screen first, then enable notifications from the installed web app (iOS 16.4 or later). Grant browser notification permission. Repeat on each device you want to receive alerts.

Push subscriptions and delivery history are stored in Supabase PostgreSQL. Keep the Supabase project active and backed up. A browser permission prompt can be declined or blocked in OS/site settings; the app will show that state. Web Push is best-effort and is not a guarantee of immediate delivery.
