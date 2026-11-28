import json
import os
import tempfile
import unittest
from unittest.mock import AsyncMock, patch
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.main import app
from app.trading import router as trading
from app.thesis import router as thesis


class ThesisReassessmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.temp.name, "thesis.sqlite3")
        self.trading_path = trading.DB_PATH
        trading.DB_PATH = self.db
        self.client = TestClient(app)
        with self.client:
            self.client.put("/api/v1/trading/instruments", json={
                "symbol": "BTCUSDT", "contract_multiplier": 1, "quantity_step": 0.001,
                "minimum_quantity": 0.001, "quote_currency": "USD", "specification_note": "Test fixture"
            })
            self.client.put("/api/v1/trading/settings", json={
                "account_equity": 10000, "account_currency": "USD", "risk_per_trade_pct": 1,
                "maximum_daily_loss_pct": 3, "maximum_simultaneous_positions": 3,
                "minimum_risk_reward": 1, "maximum_market_data_age_seconds": 300
            })
            self.client.post("/api/v1/trading/trades", json={
                "symbol": "BTCUSDT", "direction": "LONG", "entry_price": 100,
                "stop_loss": 95, "take_profit": 110, "quantity": 1, "market_price": 100,
                "market_data_timestamp": datetime.now(timezone.utc).isoformat()
            })

    def tearDown(self):
        trading.DB_PATH = self.trading_path
        self.temp.cleanup()

    def _mock_evidence(self):
        now = datetime.now(timezone.utc)
        candles = []
        for i in range(60):
            start = now - timedelta(hours=60-i)
            candles.append({"time": start.isoformat(), "close_time": (start + timedelta(hours=1)).isoformat(),
                            "open": 100+i*.1, "high": 101+i*.1, "low": 99+i*.1, "close": 100+i*.1, "volume": 10})
        return candles

    def _result(self, status):
        return {"status": status, "assessment": "Thesis evidence reviewed.", "changes": ["Momentum shifted"],
                "supporting_evidence": ["OHLCV candles"], "contradicting_evidence": [], "missing_evidence": [],
                "confidence": .8}

    def _run(self, status):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=False), \
             patch.object(thesis, "get_binance_candles", new=AsyncMock(return_value=self._mock_evidence())), \
             patch.object(thesis, "_fetch_news", new=AsyncMock(return_value=[{"title": "BTC market update", "url": "https://example.test"}])), \
             patch.object(thesis, "_ask_gemini", new=AsyncMock(return_value=(self._result(status), "test-model"))):
            return self.client.post("/api/v1/thesis/trades/1/reassess", json={
                "original_thesis": "BTC bullish continuation above support",
                "original_analysis": "Initial Gemini analysis expected higher highs and positive momentum.",
                "provider": "binance", "interval": "1h"
            })

    def test_weakened_status_persists_and_creates_one_alert(self):
        first = self._run("WEAKENED")
        second = self._run("WEAKENED")
        self.assertEqual(first.status_code, 200, first.text)
        self.assertTrue(first.json()["alert_created"])
        self.assertFalse(second.json()["alert_created"])
        history = self.client.get("/api/v1/thesis/trades/1/history").json()
        self.assertEqual(len(history["reassessments"]), 2)
        self.assertEqual(len(history["alerts"]), 1)

    def test_invalidated_is_advisory_and_does_not_close_trade(self):
        response = self._run("INVALIDATED")
        self.assertEqual(response.status_code, 200, response.text)
        trades = self.client.get("/api/v1/trading/trades?status=OPEN").json()
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0]["status"], "OPEN")

    def test_missing_original_thesis_is_rejected(self):
        response = self.client.post("/api/v1/thesis/trades/1/reassess", json={})
        self.assertEqual(response.status_code, 422)

    def test_stale_candles_are_rejected_before_gemini(self):
        candles = self._mock_evidence()
        for candle in candles:
            candle["time"] = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
            candle["close_time"] = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=False), \
             patch.object(thesis, "get_binance_candles", new=AsyncMock(return_value=candles)):
            response = self.client.post("/api/v1/thesis/trades/1/reassess", json={
                "original_thesis": "BTC bullish continuation above support",
                "original_analysis": "Initial analysis expected higher highs and positive momentum."
            })
        self.assertEqual(response.status_code, 422)

    def test_closed_trade_cannot_be_reassessed(self):
        self.client.post("/api/v1/trading/trades/1/close", json={"exit_price": 101})
        response = self.client.post("/api/v1/thesis/trades/1/reassess", json={
            "original_thesis": "BTC bullish continuation above support",
            "original_analysis": "Initial analysis expected higher highs and positive momentum."
        })
        self.assertEqual(response.status_code, 409)


if __name__ == "__main__":
    unittest.main()
