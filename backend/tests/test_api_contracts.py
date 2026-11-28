"""HTTP-level contract tests for the public API and manual Trade Desk."""
import os
import uuid
import psycopg
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.trading import router as trading_router


class ApiContractTests(unittest.TestCase):
    def setUp(self):
        self.schema = "test_" + uuid.uuid4().hex
        self.schema_patch = patch.dict(os.environ, {"DATABASE_SCHEMA": self.schema})
        self.schema_patch.start()
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.schema_patch.stop()
        with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
            conn.execute('DROP SCHEMA IF EXISTS "' + self.schema + '" CASCADE')

    def instrument(self, symbol="BTCUSDT"):
        return self.client.put("/api/v1/trading/instruments", json={
            "symbol": symbol,
            "contract_multiplier": 1,
            "quantity_step": 0.001,
            "minimum_quantity": 0.001,
            "quote_currency": "USD",
            "specification_note": "Test-only verified fixture",
        })

    def plan(self, **overrides):
        payload = {
            "symbol": "BTCUSDT",
            "direction": "LONG",
            "entry_price": 100,
            "stop_loss": 95,
            "take_profit": 110,
            "quantity": 1,
            "market_price": 100,
            "market_data_timestamp": datetime.now(timezone.utc).isoformat(),
        }
        payload.update(overrides)
        return payload

    def test_health_contract(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertEqual(response.json()["service"], "nathan-terminal-api")

    def test_overview_declares_manual_only_trade_desk(self):
        response = self.client.get("/api/v1/overview")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["trade_desk"], "manual_only")

    def test_settings_round_trip_and_cross_field_validation(self):
        settings = self.client.get("/api/v1/trading/settings")
        self.assertEqual(settings.status_code, 200)
        payload = settings.json()
        payload["account_equity"] = 25000
        saved = self.client.put("/api/v1/trading/settings", json=payload)
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.json()["account_equity"], 25000)

        payload["maximum_daily_loss_pct"] = 0.5
        invalid = self.client.put("/api/v1/trading/settings", json=payload)
        self.assertEqual(invalid.status_code, 422)

    def test_unknown_instrument_requires_review(self):
        response = self.client.post("/api/v1/trading/validate", json=self.plan())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "NEEDS_REVIEW")

    def test_naive_timestamp_requires_review(self):
        self.instrument()
        response = self.client.post("/api/v1/trading/validate", json=self.plan(
            market_data_timestamp="2026-01-01T00:00:00"
        ))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "NEEDS_REVIEW")
        self.assertIn("timezone", response.json()["reasons"][0].lower())

    def test_approved_trade_must_be_explicitly_registered_then_closed(self):
        self.instrument()
        validation = self.client.post("/api/v1/trading/validate", json=self.plan())
        self.assertEqual(validation.status_code, 200)
        self.assertEqual(validation.json()["status"], "APPROVED")

        created = self.client.post("/api/v1/trading/trades", json=self.plan())
        self.assertEqual(created.status_code, 200)
        trade = created.json()
        self.assertEqual(trade["status"], "OPEN")
        self.assertEqual(trade["quantity"], 1)

        closed = self.client.post(f"/api/v1/trading/trades/{trade['id']}/close", json={"exit_price": 110})
        self.assertEqual(closed.status_code, 200)
        self.assertEqual(closed.json()["status"], "CLOSED")
        self.assertAlmostEqual(closed.json()["realized_pnl"], 10)

        duplicate_close = self.client.post(f"/api/v1/trading/trades/{trade['id']}/close", json={"exit_price": 111})
        self.assertEqual(duplicate_close.status_code, 409)

    def test_trade_registration_rejects_unapproved_plan(self):
        self.instrument()
        response = self.client.post("/api/v1/trading/trades", json=self.plan(quantity=100))
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"]["validation"]["status"], "REJECTED")
        self.assertEqual(self.client.get("/api/v1/trading/trades").json(), [])


if __name__ == "__main__":
    unittest.main()
