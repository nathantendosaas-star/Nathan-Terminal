# Quality checks

The repository CI runs three independent jobs on every pull request targeting `main` and every push to `main`:

1. **Backend tests** — Python 3.12, pinned backend dependencies, and the standard-library unittest suite.
2. **Frontend build** — Node.js 22, TypeScript project build/type-check, and Vite production bundle.
3. **Deployment config** — Docker Compose validates the committed deployment configuration using `.env.example`.

## Run locally

Backend:

```bash
cd backend
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

Frontend:

```bash
cd frontend
npm install
npm run build
```

Compose:

```bash
docker compose --env-file .env.example config --quiet
```

The API contract suite uses an isolated temporary SQLite database and does not contact external market-data providers, Gemini, Kronos, or a broker. Test-only instrument specifications and quotes are synthetic fixtures and must never be copied into a live Trade Desk configuration.

A green CI run confirms the checked test suite and build/configuration steps pass. It does not prove live provider uptime, model inference performance, broker compatibility, trading profitability, or production security. Docker image builds and runtime smoke tests are not part of this workflow yet.
