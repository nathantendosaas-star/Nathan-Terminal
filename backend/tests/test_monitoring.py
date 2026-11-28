import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.trading import router as trading
from app.monitoring import router as monitoring


class MonitoringTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.temp.name, "monitoring.sqlite3")
        self.trading_path = trading.DB_PATH
        self.monitoring_path = monitoring.DB_PATH
        trading.DB_PATH = self.db
        monitoring.DB_PATH = self.db
        self.client = TestClient(app)
        with self.client:
            self.client.put("/api/v1/trading/instruments", json={
                "symbol": "BTCUSDT", "contract_multiplier": 1, "quantity_step": 0.001,
                "minimum_quantity": 0.001, "quote_currency": "USD",
                "specification_note": "Synthetic test fixture only"
            })
            self.client.put("/api/v1/trading/settings", json={
                "account_equity": 10000, "account_currency": "USD", "risk_per_trade_pct": 1,
                "maximum_daily_loss_pct": 3, "maximum_simultaneous_positions": 3,
                "minimum_risk_reward": 1, "maximum_market_data_age_seconds": 300
            })
            timestamp = datetime.now(timezone.utc).isoformat()
            response = self.client.post("/api/v1/trading/trades", json={
                "symbol": "BTCUSDT", "direction": "LONG", "entry_price": 100,
                "stop_loss": 95, "take_profit": 110, "quantity": 1,
                "market_price": 100, "market_data_timestamp": timestamp
            })
            self.assertEqual(response.status_code, 200, response.text)

    def tearDown(self):
        trading.DB_PATH = self.trading_path
        monitoring.DB_PATH = self.monitoring_path
        self.temp.cleanup()

    def test_snapshot_crossing_stop_creates_one_deduplicated_event(self):
        payload = {
            "symbol": "BTCUSDT", "current_price": 94, "source": "test",
            "market_data_timestamp": datetime.now(timezone.utc).isoformat()
        }
        with patch.dict(os.environ, {}, clear=True):
            first = self.client.post("/api/v1/monitoring/evaluate", json=payload)
            second = self.client.post("/api/v1/monitoring/evaluate", json=payload)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(len(first.json()["new_events"]), 1)
        self.assertEqual(first.json()["new_events"][0]["event_type"], "STOP_LOSS_TOUCHED")
        self.assertEqual(second.json()["new_events"], [])
        trades = self.client.get("/api/v1/trading/trades?status=OPEN").json()
        self.assertEqual(len(trades), 1, "Monitoring must not close the trade.")

    def test_stale_snapshot_is_rejected(self):
        payload = {
            "symbol": "BTCUSDT", "current_price": 94, "source": "test",
            "market_data_timestamp": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        }
        response = self.client.post("/api/v1/monitoring/evaluate", json=payload)
        self.assertEqual(response.status_code, 422)

    def test_status_declares_manual_only_execution(self):
        response = self.client.get("/api/v1/monitoring/status")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["automatic_execution"])
        self.assertEqual(response.json()["mode"], "snapshot_driven")


if __name__ == "__main__":
    unittest.main()
