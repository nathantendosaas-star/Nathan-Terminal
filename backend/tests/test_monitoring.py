import os
import uuid
import psycopg
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.push import service as push_service


class MonitoringTests(unittest.TestCase):
    def setUp(self):
        self.schema = "test_" + uuid.uuid4().hex
        self.schema_patch = patch.dict(os.environ, {"DATABASE_SCHEMA": self.schema})
        self.schema_patch.start()
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
        self.schema_patch.stop()
        with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
            conn.execute('DROP SCHEMA IF EXISTS "' + self.schema + '" CASCADE')

    def test_snapshot_crossing_stop_creates_one_deduplicated_event(self):
        payload = {
            "symbol": "BTCUSDT", "current_price": 94, "source": "test",
            "market_data_timestamp": datetime.now(timezone.utc).isoformat()
        }
        with patch.dict(os.environ, {"VAPID_SUBJECT": "mailto:test@example.com"}):
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

    def test_push_public_key_and_subscription_are_persisted(self):
        key = self.client.get("/api/v1/push/public-key")
        self.assertEqual(key.status_code, 200)
        self.assertGreater(len(key.json()["public_key"]), 60)
        body = {
            "endpoint": "https://push.example.test/subscription/one",
            "keys": {"p256dh": "p" * 65, "auth": "a" * 24},
            "device_name": "Android phone",
        }
        saved = self.client.post("/api/v1/push/subscribe", json=body)
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertEqual(saved.json()["active_devices"], 1)
        status = self.client.get("/api/v1/push/status")
        self.assertTrue(status.json()["enabled"])
        self.assertEqual(status.json()["active_devices"], 1)
        removed = self.client.post("/api/v1/push/unsubscribe", json={"endpoint": body["endpoint"]})
        self.assertEqual(removed.json()["active_devices"], 0)

    def test_monitoring_event_is_delivered_to_registered_device(self):
        self.client.post("/api/v1/push/subscribe", json={
            "endpoint": "https://push.example.test/subscription/deliver",
            "keys": {"p256dh": "p" * 65, "auth": "a" * 24},
            "device_name": "Test phone",
        })
        payload = {
            "symbol": "BTCUSDT", "current_price": 94, "source": "test",
            "market_data_timestamp": datetime.now(timezone.utc).isoformat()
        }
        with patch("app.push.service.webpush") as send:
            response = self.client.post("/api/v1/monitoring/evaluate", json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["new_events"][0]["delivery_status"], "delivered")
        self.assertEqual(send.call_count, 1)
        self.assertIn("STOP LOSS", send.call_args.kwargs["data"].upper())

    def test_failed_push_can_be_retried(self):
        self.client.post("/api/v1/push/subscribe", json={
            "endpoint": "https://push.example.test/subscription/retry",
            "keys": {"p256dh": "p" * 65, "auth": "a" * 24},
            "device_name": "Retry phone",
        })
        payload = {
            "symbol": "BTCUSDT", "current_price": 94, "source": "test",
            "market_data_timestamp": datetime.now(timezone.utc).isoformat()
        }
        with patch("app.push.service.webpush", side_effect=RuntimeError("temporary")):
            created = self.client.post("/api/v1/monitoring/evaluate", json=payload)
        event = created.json()["new_events"][0]
        self.assertEqual(event["delivery_status"], "failed")
        with patch("app.push.service.webpush") as send:
            retried = self.client.post(f"/api/v1/monitoring/events/{event['id']}/retry")
        self.assertEqual(retried.status_code, 200)
        self.assertEqual(retried.json()["delivery_status"], "delivered")
        self.assertEqual(send.call_count, 1)

    def test_expired_push_endpoint_is_removed(self):
        self.client.post("/api/v1/push/subscribe", json={
            "endpoint": "https://push.example.test/subscription/expired",
            "keys": {"p256dh": "p" * 65, "auth": "a" * 24},
            "device_name": "Expired phone",
        })
        from pywebpush import WebPushException
        class GoneResponse:
            status_code = 410
        error = WebPushException("gone", response=GoneResponse())
        payload = {
            "symbol": "BTCUSDT", "current_price": 94, "source": "test",
            "market_data_timestamp": datetime.now(timezone.utc).isoformat()
        }
        with patch("app.push.service.webpush", side_effect=error):
            response = self.client.post("/api/v1/monitoring/evaluate", json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get("/api/v1/push/status").json()["active_devices"], 0)


if __name__ == "__main__":
    unittest.main()
