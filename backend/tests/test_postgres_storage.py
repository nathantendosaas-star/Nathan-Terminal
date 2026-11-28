"""PostgreSQL integration smoke tests; CI runs these against PostgreSQL 17."""
import os
import unittest

from fastapi.testclient import TestClient

from app.database import connect_postgres
from app.main import app


class PostgresStorageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.getenv("DATABASE_URL"):
            raise unittest.SkipTest("DATABASE_URL is not configured")
        cls.client = TestClient(app)

    def test_private_schema_and_persistent_tables(self):
        with connect_postgres() as conn:
            schema = conn.execute("SELECT current_schema() AS schema").fetchone()
            self.assertEqual(schema["schema"], "app")
            rows = conn.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema='app'"
            ).fetchall()
            names = {row["table_name"] for row in rows}
            self.assertTrue({
                "settings", "instruments", "trades", "app_settings",
                "monitoring_events", "push_subscriptions",
                "monitoring_push_deliveries", "market_sessions",
                "trade_theses", "thesis_reassessments", "thesis_alerts",
            }.issubset(names))

    def test_trade_settings_round_trip(self):
        response = self.client.get("/api/v1/trading/settings")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        payload["account_equity"] = 12500
        updated = self.client.put("/api/v1/trading/settings", json=payload)
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["account_equity"], 12500)

    def test_market_session_lifecycle_persists(self):
        current = self.client.get("/api/v1/sessions/current")
        self.assertEqual(current.status_code, 200)
        started = self.client.post("/api/v1/sessions/start", json={
            "symbols": ["BTCUSDT", "ETHUSDT"], "interval": "1h"
        })
        self.assertEqual(started.status_code, 200, started.text)
        session_id = started.json()["session"]["id"]
        stopped = self.client.post(f"/api/v1/sessions/{session_id}/stop")
        self.assertEqual(stopped.status_code, 200, stopped.text)
        history = self.client.get("/api/v1/sessions/history")
        self.assertEqual(history.status_code, 200)
        self.assertTrue(any(item["id"] == session_id for item in history.json()["sessions"]))


if __name__ == "__main__":
    unittest.main()
