"""Deterministic technical indicators and simple swing-structure analysis."""
from __future__ import annotations

from typing import Any


def _sma(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def _ema_series(values: list[float | None], period: int) -> list[float | None]:
    """EMA seeded with an SMA of the first complete window."""
    result: list[float | None] = [None] * len(values)
    window: list[float] = []
    previous: float | None = None
    alpha = 2 / (period + 1)
    for index, value in enumerate(values):
        if value is None:
            continue
        if previous is None:
            window.append(value)
            if len(window) == period:
                previous = sum(window) / period
                result[index] = previous
        else:
            previous = (value * alpha) + (previous * (1 - alpha))
            result[index] = previous
    return result


def _rsi_wilder(closes: list[float], period: int = 14) -> float | None:
    if len(closes) <= period:
        return None
    changes = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [max(change, 0.0) for change in changes]
    losses = [max(-change, 0.0) for change in changes]
    average_gain = sum(gains[:period]) / period
    average_loss = sum(losses[:period]) / period
    for index in range(period, len(changes)):
        average_gain = ((average_gain * (period - 1)) + gains[index]) / period
        average_loss = ((average_loss * (period - 1)) + losses[index]) / period
    if average_loss == 0:
        return 50.0 if average_gain == 0 else 100.0
    relative_strength = average_gain / average_loss
    return 100 - (100 / (1 + relative_strength))


def _atr_wilder(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> float | None:
    if len(closes) <= period:
        return None
    true_ranges = []
    for index in range(1, len(closes)):
        true_ranges.append(max(
            highs[index] - lows[index],
            abs(highs[index] - closes[index - 1]),
            abs(lows[index] - closes[index - 1]),
        ))
    atr = sum(true_ranges[:period]) / period
    for value in true_ranges[period:]:
        atr = ((atr * (period - 1)) + value) / period
    return atr


def _swing_points(values: list[float], side: str, radius: int = 2) -> list[tuple[int, float]]:
    points: list[tuple[int, float]] = []
    for index in range(radius, len(values) - radius):
        left = values[index - radius:index]
        right = values[index + 1:index + radius + 1]
        current = values[index]
        if side == "high" and all(current > item for item in left + right):
            points.append((index, current))
        elif side == "low" and all(current < item for item in left + right):
            points.append((index, current))
    return points


def calculate_technical_analysis(candles: list[dict[str, Any]]) -> dict[str, Any]:
    """Calculate indicators from chronological OHLCV candles; no trade signals are emitted."""
    if not candles:
        raise ValueError("At least one candle is required.")

    closes = [float(candle["close"]) for candle in candles]
    highs = [float(candle["high"]) for candle in candles]
    lows = [float(candle["low"]) for candle in candles]
    latest = closes[-1]

    ema20_series = _ema_series(closes, 20)
    ema50_series = _ema_series(closes, 50)
    macd_fast = _ema_series(closes, 12)
    macd_slow = _ema_series(closes, 26)
    macd_line: list[float | None] = [
        fast - slow if fast is not None and slow is not None else None
        for fast, slow in zip(macd_fast, macd_slow)
    ]
    signal_series = _ema_series(macd_line, 9)
    valid_macd = next((value for value in reversed(macd_line) if value is not None), None)
    valid_signal = next((value for value in reversed(signal_series) if value is not None), None)
    histogram = valid_macd - valid_signal if valid_macd is not None and valid_signal is not None else None

    swing_highs = _swing_points(highs, "high")
    swing_lows = _swing_points(lows, "low")
    structure = "insufficient_data"
    if len(swing_highs) >= 2 and len(swing_lows) >= 2:
        higher_highs = swing_highs[-1][1] > swing_highs[-2][1]
        higher_lows = swing_lows[-1][1] > swing_lows[-2][1]
        lower_highs = swing_highs[-1][1] < swing_highs[-2][1]
        lower_lows = swing_lows[-1][1] < swing_lows[-2][1]
        if higher_highs and higher_lows:
            structure = "higher_highs_higher_lows"
        elif lower_highs and lower_lows:
            structure = "lower_highs_lower_lows"
        else:
            structure = "mixed_or_transitioning"

    support = swing_lows[-1][1] if swing_lows else None
    resistance = swing_highs[-1][1] if swing_highs else None

    def level(value: float | None) -> dict[str, float | None] | None:
        if value is None:
            return None
        distance = ((latest - value) / value) * 100 if value else None
        return {"price": round(value, 8), "distance_from_close_pct": round(distance, 4) if distance is not None else None}

    def rounded(value: float | None) -> float | None:
        return round(value, 8) if value is not None else None

    return {
        "method": "deterministic_ohlcv",
        "candle_count": len(candles),
        "latest_close": rounded(latest),
        "rsi_14": rounded(_rsi_wilder(closes)),
        "macd": {
            "line": rounded(valid_macd),
            "signal": rounded(valid_signal),
            "histogram": rounded(histogram),
        },
        "moving_averages": {
            "ema_20": rounded(next((value for value in reversed(ema20_series) if value is not None), None)),
            "ema_50": rounded(next((value for value in reversed(ema50_series) if value is not None), None)),
            "sma_20": rounded(_sma(closes, 20)),
            "sma_50": rounded(_sma(closes, 50)),
        },
        "atr_14": rounded(_atr_wilder(highs, lows, closes)),
        "support": level(support),
        "resistance": level(resistance),
        "market_structure": structure,
        "notes": [
            "Indicators describe historical price action and are not predictions.",
            "Support and resistance are the latest confirmed two-sided swing points, not guaranteed levels.",
            "No buy, sell, or position-sizing recommendation is generated.",
        ],
    }
