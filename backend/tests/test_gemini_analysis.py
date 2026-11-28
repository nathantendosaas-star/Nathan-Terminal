import os, tempfile, unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from app.analysis.router import GEMINI_MODELS, DEFAULT_GEMINI_MODEL

from app.analysis.router import AnalysisRequest, build_analysis_prompt


class GeminiAnalysisTests(unittest.TestCase):
    def test_prompt_contains_market_context_and_safety_instructions(self):
        candles = [{"time": "2026-01-01T00:00:00+00:00", "open": 10, "high": 12, "low": 9, "close": 11, "volume": 100}]
        prompt = build_analysis_prompt("BTCUSDT", "1h", candles, {"rsi_14": 55}, "Explain momentum")
        self.assertIn("BTCUSDT", prompt)
        self.assertIn("Explain momentum", prompt)
        self.assertIn("Never issue personalized investment advice", prompt)
        self.assertIn("2026-01-01", prompt)

    def test_model_catalog_uses_current_flash_models(self):
        self.assertEqual(DEFAULT_GEMINI_MODEL, "gemini-3.8-flash")
        self.assertEqual(GEMINI_MODELS, ("gemini-3.8-flash", "gemini-3.6-flash"))

    def test_model_selection_is_persisted_and_reported_by_backend(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
            "APP_PASSWORD_HASH": "", "AUTH_DB_PATH": os.path.join(directory, "settings.sqlite3"),
            "GEMINI_API_KEY": "test-key", "GEMINI_MODEL": "gemini-2.5-flash",
        }):
            client = TestClient(app)
            try:
                selected = client.put("/api/v1/analysis/model", json={"model": "gemini-3.6-flash"})
                self.assertEqual(selected.status_code, 200)
                status = client.get("/api/v1/analysis/status")
                self.assertEqual(status.json()["model"], "gemini-3.6-flash")
                self.assertEqual(status.json()["models"], ["gemini-3.8-flash", "gemini-3.6-flash"])
            finally:
                client.close()

    def test_request_defaults(self):
        request = AnalysisRequest(symbol="BTCUSDT")
        self.assertEqual(request.provider, "binance")
        self.assertEqual(request.interval, "1h")
        self.assertTrue(request.question)


if __name__ == "__main__":
    unittest.main()
