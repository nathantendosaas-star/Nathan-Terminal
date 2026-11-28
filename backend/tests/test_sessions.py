"""Session lifecycle API contract tests."""
import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.sessions import router as sessions_router


class SessionLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "sessions.sqlite3")
        self.db_patch = patch.object(sessions_router, "DB_PATH", self.db_path)
        self.db_patch.start()
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.db_patch.stop()
        self.temp_dir.cleanup()

    def test_starts_eight_hour_session_with_explicit_market_subscriptions(self):
        response = self.client.post("/api/v1/sessions/start", json={})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["active"])
        session = payload["session"]
        self.assertEqual(session["status"], "ACTIVE")
        self.assertEqual(session["maximum_duration_hours"], 8)
        started = datetime.fromisoformat(session["started_at"])
        expires = datetime.fromisoformat(session["expires_at"])
        self.assertEqual(expires - started, timedelta(hours=8))
        self.assertEqual(
            [item["symbol"] for item in session["subscriptions"]],
            ["BTCUSDT", "ETHUSDT", "SOLUSDT", "NVDA", "AAPL", "GOOGL"],
        )

    def test_only_one_active_session_is_allowed(self):
        first = self.client.post("/api/v1/sessions/start", json={})
        second = self.client.post("/api/v1/sessions/start", json={})
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 409)

    def test_stop_ends_session_and_preserves_history(self):
        started = self.client.post("/api/v1/sessions/start", json={}).json()["session"]
        stopped = self.client.post(f"/api/v1/sessions/{started['id']}/stop")
        self.assertEqual(stopped.status_code, 200)
        self.assertEqual(stopped.json()["session"]["status"], "STOPPED")
        self.assertIsNotNone(stopped.json()["session"]["ended_at"])
        self.assertFalse(self.client.get("/api/v1/sessions/current").json()["active"])
        history = self.client.get("/api/v1/sessions/history").json()["sessions"]
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["id"], started["id"])

    def test_expired_session_is_automatically_marked_expired(self):
        started = self.client.post("/api/v1/sessions/start", json={}).json()["session"]
        with sqlite3.connect(self.db_path) as conn:
            past = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
            conn.execute("UPDATE market_sessions SET expires_at=? WHERE id=?", (past, started["id"]))
        current = self.client.get("/api/v1/sessions/current").json()
        self.assertFalse(current["active"])
        history = self.client.get("/api/v1/sessions/history").json()["sessions"]
        self.assertEqual(history[0]["status"], "EXPIRED")
        self.assertIsNotNone(history[0]["ended_at"])

    def test_unknown_or_duplicate_symbols_are_rejected(self):
        unsupported = self.client.post("/api/v1/sessions/start", json={"symbols": ["BTCUSDT", "UNKNOWN"]})
        duplicate = self.client.post("/api/v1/sessions/start", json={"symbols": ["BTCUSDT", "BTCUSDT"]})
        self.assertEqual(unsupported.status_code, 422)
        self.assertEqual(duplicate.status_code, 422)

    def test_stopped_session_cannot_be_reactivated_by_stop_endpoint(self):
        started = self.client.post("/api/v1/sessions/start", json={}).json()["session"]
        self.client.post(f"/api/v1/sessions/{started['id']}/stop")
        repeated = self.client.post(f"/api/v1/sessions/{started['id']}/stop")
        self.assertEqual(repeated.status_code, 200)
        self.assertEqual(repeated.json()["session"]["status"], "STOPPED")


if __name__ == "__main__":
    unittest.main()
