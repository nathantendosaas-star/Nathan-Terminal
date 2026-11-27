import pytest

from app.forecasting.kronos import KronosUnavailable, forecast_candles, model_status


def sample_candles(count=40):
    from datetime import datetime, timedelta, timezone

    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [
        {
            "time": (start + timedelta(hours=index)).isoformat().replace("+00:00", "Z"),
            "open": 100 + index,
            "high": 102 + index,
            "low": 99 + index,
            "close": 101 + index,
            "volume": 1000 + index,
        }
        for index in range(count)
    ]


def test_requires_minimum_history():
    with pytest.raises(ValueError, match="At least 32"):
        forecast_candles(sample_candles(20), "1h")


def test_rejects_invalid_prediction_horizon():
    with pytest.raises(ValueError, match="between 1 and 48"):
        forecast_candles(sample_candles(), "1h", 49)


def test_status_is_safe_before_model_load():
    status = model_status()
    assert status["model"] == "NeoQuasar/Kronos-mini"
    assert status["loaded"] is False


def test_missing_vendor_source_fails_explicitly(monkeypatch, tmp_path):
    import app.forecasting.kronos as kronos

    monkeypatch.setattr(kronos, "SOURCE_PATH", tmp_path / "missing")
    monkeypatch.setattr(kronos, "_predictor", None)
    with pytest.raises(KronosUnavailable, match="Kronos source is not installed"):
        kronos._load_predictor()
