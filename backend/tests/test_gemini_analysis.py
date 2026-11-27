import unittest

from app.analysis.router import AnalysisRequest, build_analysis_prompt


class GeminiAnalysisTests(unittest.TestCase):
    def test_prompt_contains_market_context_and_safety_instructions(self):
        candles = [{"time": "2026-01-01T00:00:00+00:00", "open": 10, "high": 12, "low": 9, "close": 11, "volume": 100}]
        prompt = build_analysis_prompt("BTCUSDT", "1h", candles, {"rsi_14": 55}, "Explain momentum")
        self.assertIn("BTCUSDT", prompt)
        self.assertIn("Explain momentum", prompt)
        self.assertIn("Never issue personalized investment advice", prompt)
        self.assertIn("2026-01-01", prompt)

    def test_request_defaults(self):
        request = AnalysisRequest(symbol="BTCUSDT")
        self.assertEqual(request.provider, "binance")
        self.assertEqual(request.interval, "1h")
        self.assertTrue(request.question)


if __name__ == "__main__":
    unittest.main()
