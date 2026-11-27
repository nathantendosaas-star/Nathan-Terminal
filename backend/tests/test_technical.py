import unittest

from app.market_data.technical import calculate_technical_analysis


def make_candles(closes: list[float]) -> list[dict]:
    return [
        {
            "time": f"2026-01-{(index % 28) + 1:02d}T00:00:00+00:00",
            "open": close - 0.5,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": 100.0,
        }
        for index, close in enumerate(closes)
    ]


class TechnicalAnalysisTests(unittest.TestCase):
    def test_returns_null_for_indicators_without_enough_history(self):
        result = calculate_technical_analysis(make_candles([100.0, 101.0, 102.0]))
        self.assertIsNone(result["rsi_14"])
        self.assertIsNone(result["moving_averages"]["ema_20"])
        self.assertIsNone(result["macd"]["histogram"])
        self.assertEqual(result["market_structure"], "insufficient_data")

    def test_flat_market_rsi_is_neutral(self):
        result = calculate_technical_analysis(make_candles([100.0] * 80))
        self.assertEqual(result["rsi_14"], 50.0)

    def test_up_only_market_rsi_is_100(self):
        result = calculate_technical_analysis(make_candles([100.0 + index for index in range(80)]))
        self.assertEqual(result["rsi_14"], 100.0)

    def test_moving_averages_and_macd_are_available_with_history(self):
        result = calculate_technical_analysis(make_candles([100.0 + index * 0.25 for index in range(100)]))
        self.assertIsNotNone(result["moving_averages"]["ema_20"])
        self.assertIsNotNone(result["moving_averages"]["ema_50"])
        self.assertIsNotNone(result["moving_averages"]["sma_20"])
        self.assertIsNotNone(result["moving_averages"]["sma_50"])
        self.assertIsNotNone(result["macd"]["line"])
        self.assertIsNotNone(result["macd"]["signal"])
        self.assertIsNotNone(result["macd"]["histogram"])
        self.assertGreater(result["atr_14"], 0)


if __name__ == "__main__":
    unittest.main()
