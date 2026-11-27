import os
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from app.market_data.twelve_data import (
    INTERVALS,
    _normalize_values,
    get_twelve_data_candles,
)


class TwelveDataNormalizationTests(unittest.TestCase):
    def test_normalizes_newest_first_provider_values_to_chronological_utc(self):
        values = [
            {"datetime": "2026-03-02 11:00:00", "open": "12", "high": "14", "low": "11", "close": "13", "volume": "200"},
            {"datetime": "2026-03-02 10:00:00", "open": "10", "high": "13", "low": "9", "close": "12", "volume": "150"},
        ]
        candles = _normalize_values(values, "1h")
        self.assertEqual(candles[0]["time"], "2026-03-02T10:00:00+00:00")
        self.assertEqual(candles[0]["close_time"], "2026-03-02T11:00:00+00:00")
        self.assertEqual(candles[1]["close"], 13.0)

    def test_month_interval_advances_to_next_month(self):
        values = [{"datetime": "2026-12-01 00:00:00", "open": "1", "high": "2", "low": "1", "close": "2"}]
        candle = _normalize_values(values, "1M")[0]
        self.assertEqual(candle["close_time"], "2027-01-01T00:00:00+00:00")

    def test_invalid_rows_are_skipped(self):
        self.assertEqual(_normalize_values([{"datetime": "not-a-date"}], "1h"), [])

    def test_supported_interval_mapping_is_explicit(self):
        self.assertEqual(INTERVALS["1h"][0], "1h")
        self.assertEqual(INTERVALS["1d"][0], "1day")


class TwelveDataConfigurationTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_api_key_fails_without_network_request(self):
        with patch.dict(os.environ, {"TWELVE_DATA_API_KEY": ""}):
            with self.assertRaises(HTTPException) as raised:
                await get_twelve_data_candles("AAPL")
        self.assertEqual(raised.exception.status_code, 503)

    async def test_unsupported_interval_is_rejected(self):
        with self.assertRaises(HTTPException) as raised:
            await get_twelve_data_candles("AAPL", interval="3h")
        self.assertEqual(raised.exception.status_code, 422)

    async def test_invalid_symbol_is_rejected(self):
        with self.assertRaises(HTTPException) as raised:
            await get_twelve_data_candles("../secret")
        self.assertEqual(raised.exception.status_code, 422)


if __name__ == "__main__":
    unittest.main()
