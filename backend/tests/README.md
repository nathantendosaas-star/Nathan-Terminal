# Backend tests

Run the API and deterministic risk-engine test suite from the backend directory:

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

The API contract tests use FastAPI's HTTP test client and a temporary SQLite database. They do not call live market-data providers, Gemini, Kronos, or a broker. The fixtures use synthetic test-only instrument specifications and prices; they are not trading recommendations or real instrument metadata.
