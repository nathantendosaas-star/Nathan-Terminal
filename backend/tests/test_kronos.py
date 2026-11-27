import unittest

from app.forecasting.kronos import KronosUnavailable, forecast_candles, model_status


def sample_candles(count=40):
    from datetime import datetime, timedelta, timezone
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [{
        "time": (start + timedelta(hours=index)).isoformat().replace("+00:00", "Z"),
        "open": 100 + index, "high": 102 + index, "low": 99 + index,
        "close": 101 + index, "volume": 1000 + index,
    } for index in range(count)]


class KronosIntegrationTests(unittest.TestCase):
    def test_requires_minimum_history(self):
        with self.assertRaisesRegex(ValueError, "At least 32"):
            forecast_candles(sample_candles(20), "1h")

    def test_rejects_invalid_prediction_horizon(self):
        with self.assertRaisesRegex(ValueError, "between 1 and 48"):
            forecast_candles(sample_candles(), "1h", 49)

    def test_status_is_safe_before_model_load(self):
        status = model_status()
        self.assertEqual(status["model"], "NeoQuasar/Kronos-mini")
        self.assertFalse(status["loaded"])

    def test_missing_vendor_source_fails_explicitly(self):
        import app.forecasting.kronos as kronos
        original_path, original_predictor = kronos.SOURCE_PATH, kronos._predictor
        try:
            kronos.SOURCE_PATH = kronos.SOURCE_PATH / "__missing_test_source__"
            kronos._predictor = None
            with self.assertRaisesRegex(KronosUnavailable, "Kronos source is not installed"):
                kronos._load_predictor()
        finally:
            kronos.SOURCE_PATH, kronos._predictor = original_path, original_predictor


if __name__ == "__main__":
    unittest.main()
