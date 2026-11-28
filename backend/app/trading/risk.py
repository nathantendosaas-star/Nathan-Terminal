"""Deterministic, broker-independent trade risk calculations."""
from __future__ import annotations

import math
from typing import Any


def floor_to_step(value: float, step: float) -> float:
    if step <= 0:
        raise ValueError("Quantity step must be positive.")
    return math.floor((value + 1e-12) / step) * step


def calculate_plan(plan: dict[str, Any], settings: dict[str, Any], instrument: dict[str, Any], open_positions: int, daily_realized_pnl: float, open_risk: float) -> dict[str, Any]:
    entry, stop, target = (float(plan[key]) for key in ("entry_price", "stop_loss", "take_profit"))
    direction = plan["direction"]
    if not all(math.isfinite(value) and value > 0 for value in (entry, stop, target)):
        return {"status": "REJECTED", "reasons": ["Entry, stop-loss and take-profit must be finite positive prices."]}
    if direction == "LONG" and not (stop < entry < target):
        return {"status": "REJECTED", "reasons": ["For a LONG plan, stop-loss must be below entry and take-profit above entry."]}
    if direction == "SHORT" and not (target < entry < stop):
        return {"status": "REJECTED", "reasons": ["For a SHORT plan, take-profit must be below entry and stop-loss above entry."]}

    multiplier = float(instrument["contract_multiplier"])
    step = float(instrument["quantity_step"])
    minimum = float(instrument["minimum_quantity"])
    if multiplier <= 0 or step <= 0 or minimum < 0:
        return {"status": "NEEDS_REVIEW", "reasons": ["Instrument specification is invalid; verify contract multiplier and broker quantity constraints."]}

    distance_risk = abs(entry - stop) * multiplier
    distance_reward = abs(target - entry) * multiplier
    rr = distance_reward / distance_risk if distance_risk else 0
    equity = float(settings["account_equity"])
    risk_pct = float(settings["risk_per_trade_pct"])
    risk_budget = equity * risk_pct / 100
    suggested_qty = floor_to_step(risk_budget / distance_risk, step) if distance_risk else 0
    suggested_risk = suggested_qty * distance_risk
    qty = plan.get("quantity")
    reasons: list[str] = []
    review: list[str] = []

    if rr < float(settings["minimum_risk_reward"]):
        reasons.append(f"Risk/reward {rr:.2f}:1 is below the configured minimum of {settings['minimum_risk_reward']:.2f}:1.")
    if open_positions >= int(settings["maximum_simultaneous_positions"]):
        reasons.append("Maximum simultaneous open positions has been reached.")
    if suggested_qty < minimum or suggested_qty <= 0:
        review.append("Risk budget produces a quantity below the instrument minimum; no valid size can be suggested.")
    if qty is None:
        review.append("No order quantity supplied. Suggested size is informational; enter the exact intended quantity before registration.")
    else:
        qty = float(qty)
        if not math.isfinite(qty) or qty <= 0:
            reasons.append("Quantity must be a finite positive number.")
        elif qty < minimum:
            reasons.append(f"Quantity is below the instrument minimum of {minimum}.")
        elif abs(qty / step - round(qty / step)) > 1e-7:
            reasons.append(f"Quantity must respect the instrument step of {step}.")
        else:
            actual_risk = qty * distance_risk
            if actual_risk > risk_budget + 1e-8:
                reasons.append(f"Planned quantity risks {actual_risk:.2f}, above the per-trade budget {risk_budget:.2f}.")
    new_trade_risk = risk_budget if qty is None or not math.isfinite(float(qty)) or float(qty) <= 0 else float(qty) * distance_risk
    projected_daily_loss = max(0.0, -daily_realized_pnl) + open_risk + new_trade_risk
    daily_limit = equity * float(settings["maximum_daily_loss_pct"]) / 100
    if projected_daily_loss > daily_limit + 1e-9:
        reasons.append(f"Projected daily loss exposure {projected_daily_loss:.2f} exceeds the configured daily limit {daily_limit:.2f}.")
    if reasons:
        status = "REJECTED"
    elif review:
        status = "NEEDS_REVIEW"
    else:
        status = "APPROVED"
    return {
        "status": status,
        "reasons": reasons + review,
        "symbol": plan["symbol"].upper(),
        "direction": direction,
        "risk_reward": round(rr, 4),
        "risk_budget": round(risk_budget, 8),
        "risk_per_unit": round(distance_risk, 10),
        "suggested_quantity": suggested_qty,
        "suggested_risk_amount": round(suggested_risk, 8),
        "planned_quantity": qty,
        "planned_risk_amount": round(qty * distance_risk, 8) if qty is not None and qty > 0 else None,
        "reward_amount": round((qty if qty is not None and qty > 0 else suggested_qty) * distance_reward, 8),
        "open_positions": open_positions,
        "daily_realized_pnl": round(daily_realized_pnl, 8),
        "projected_daily_loss_exposure": round(projected_daily_loss, 8),
        "daily_loss_limit": round(daily_limit, 8),
        "instrument": instrument,
        "note": "Sizing uses the configured contract multiplier and broker quantity step. Verify instrument specifications before relying on the result.",
    }
