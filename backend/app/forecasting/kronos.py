from __future__ import annotations

import math
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any


MODEL_ID = os.getenv("KRONOS_MODEL_ID", "NeoQuasar/Kronos-mini")
TOKENIZER_ID = os.getenv("KRONOS_TOKENIZER_ID", "NeoQuasar/Kronos-Tokenizer-2k")
MAX_CONTEXT = int(os.getenv("KRONOS_MAX_CONTEXT", "2048"))
DEFAULT_PRED_LEN = int(os.getenv("KRONOS_PRED_LEN", "24"))
SOURCE_PATH = Path(os.getenv("KRONOS_SOURCE_PATH", Path(__file__).resolve().parents[2] / "vendor" / "Kronos"))

_lock = threading.Lock()
_predictor: Any | None = None
_model_status: dict[str, Any] = {
    "loaded": False,
    "model": MODEL_ID,
    "tokenizer": TOKENIZER_ID,
    "device": None,
    "load_seconds": None,
    "error": None,
}


class KronosUnavailable(RuntimeError):
    pass


def model_status() -> dict[str, Any]:
    return dict(_model_status)


def _load_predictor() -> Any:
    global _predictor
    if _predictor is not None:
        return _predictor
    with _lock:
        if _predictor is not None:
            return _predictor
        if not SOURCE_PATH.exists():
            raise KronosUnavailable(
                "Kronos source is not installed. Clone shiyu-coder/Kronos into "
                f"{SOURCE_PATH} or set KRONOS_SOURCE_PATH."
            )
        sys.path.insert(0, str(SOURCE_PATH))
        started = time.perf_counter()
        try:
            import torch
            from model import Kronos, KronosPredictor, KronosTokenizer

            device = "cuda:0" if torch.cuda.is_available() else "cpu"
            tokenizer = KronosTokenizer.from_pretrained(TOKENIZER_ID)
            model = Kronos.from_pretrained(MODEL_ID)
            model = model.to(device)
            model.eval()
            _predictor = KronosPredictor(model, tokenizer, max_context=MAX_CONTEXT, device=device)
            _model_status.update({
                "loaded": True,
                "device": device,
                "load_seconds": round(time.perf_counter() - started, 3),
                "error": None,
            })
            return _predictor
        except Exception as exc:
            _model_status["error"] = f"{type(exc).__name__}: {exc}"
            raise KronosUnavailable(f"Could not load Kronos-mini: {_model_status['error']}") from exc


def forecast_candles(candles: list[dict[str, Any]], interval: str, pred_len: int = DEFAULT_PRED_LEN) -> dict[str, Any]:
    if len(candles) < 32:
        raise ValueError("At least 32 historical candles are required for a Kronos forecast.")
    if pred_len < 1 or pred_len > 48:
        raise ValueError("pred_len must be between 1 and 48.")

    import pandas as pd

    frame = pd.DataFrame(candles)
    frame["timestamps"] = pd.to_datetime(frame["time"], utc=True).dt.tz_localize(None)
    frame = frame[["timestamps", "open", "high", "low", "close", "volume"]].copy()
    for column in ("open", "high", "low", "close", "volume"):
        frame[column] = pd.to_numeric(frame[column], errors="raise")
    if not all(math.isfinite(float(value)) for value in frame[["open", "high", "low", "close", "volume"]].to_numpy().ravel()):
        raise ValueError("Historical OHLCV values must be finite numbers.")
    frame = frame.tail(MAX_CONTEXT).reset_index(drop=True)

    step = {
        "1m": pd.Timedelta(minutes=1), "5m": pd.Timedelta(minutes=5),
        "15m": pd.Timedelta(minutes=15), "30m": pd.Timedelta(minutes=30),
        "1h": pd.Timedelta(hours=1), "2h": pd.Timedelta(hours=2),
        "4h": pd.Timedelta(hours=4), "1d": pd.Timedelta(days=1),
        "1w": pd.Timedelta(weeks=1), "1M": pd.DateOffset(months=1),
    }.get(interval)
    if step is None:
        raise ValueError(f"Unsupported forecast interval: {interval}")

    predictor = _load_predictor()
    last_timestamp = pd.Timestamp(frame["timestamps"].iloc[-1])
    if isinstance(step, pd.DateOffset):
        future_times = pd.Series([last_timestamp + step * i for i in range(1, pred_len + 1)])
    else:
        future_times = pd.Series([last_timestamp + step * i for i in range(1, pred_len + 1)])

    started = time.perf_counter()
    prediction = predictor.predict(
        df=frame[["open", "high", "low", "close", "volume"]],
        x_timestamp=frame["timestamps"],
        y_timestamp=future_times,
        pred_len=pred_len,
        T=1.0,
        top_p=0.9,
        sample_count=1,
    )
    inference_seconds = time.perf_counter() - started
    forecast = []
    for timestamp, row in prediction.iterrows():
        values = {key: float(row[key]) for key in ("open", "high", "low", "close", "volume")}
        if not all(math.isfinite(value) for value in values.values()):
            raise RuntimeError("Kronos returned non-finite forecast values.")
        high = max(values["high"], values["open"], values["close"], values["low"])
        low = min(values["low"], values["open"], values["close"], values["high"])
        forecast.append({
            "time": pd.Timestamp(timestamp).tz_localize("UTC").isoformat().replace("+00:00", "Z"),
            **values,
            "high": high,
            "low": low,
        })

    memory_mb = None
    try:
        import resource
        memory_mb = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 if sys.platform != "darwin" else 1024 * 1024), 2)
    except (ImportError, OSError, ValueError):
        pass

    return {
        "model": MODEL_ID,
        "device": _model_status.get("device"),
        "historical_count": len(frame),
        "forecast_count": len(forecast),
        "inference_ms": round(inference_seconds * 1000, 2),
        "process_peak_memory_mb": memory_mb,
        "historical_candles": [
            {key: (pd.Timestamp(row["timestamps"]).tz_localize("UTC").isoformat().replace("+00:00", "Z") if key == "time" else float(row[key]))
             for key in ("time", "open", "high", "low", "close", "volume")}
            for _, row in frame.iterrows()
        ],
        "forecast_candles": forecast,
        "disclaimer": "Model estimates, not trading signals. Forecast candles are separate from observed market history.",
    }
