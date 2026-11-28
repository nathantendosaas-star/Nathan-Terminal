import unittest

from app.trading.risk import calculate_plan, floor_to_step


class RiskEngineTests(unittest.TestCase):
    def setUp(self):
        self.settings = {"account_equity": 10000, "risk_per_trade_pct": 1, "maximum_daily_loss_pct": 3, "maximum_simultaneous_positions": 3, "minimum_risk_reward": 2}
        self.instrument = {"symbol": "BTCUSDT", "contract_multiplier": 1, "quantity_step": 0.001, "minimum_quantity": 0.001}

    def test_position_size_and_reward_risk(self):
        plan = {"symbol": "BTCUSDT", "direction": "LONG", "entry_price": 100, "stop_loss": 95, "take_profit": 110, "quantity": 2}
        result = calculate_plan(plan, self.settings, self.instrument, 0, 0, 0)
        self.assertEqual(result["status"], "APPROVED")
        self.assertEqual(result["suggested_quantity"], 20)
        self.assertEqual(result["risk_reward"], 2)
        self.assertEqual(result["planned_risk_amount"], 10)

    def test_rejects_risk_above_budget(self):
        plan = {"symbol": "BTCUSDT", "direction": "LONG", "entry_price": 100, "stop_loss": 95, "take_profit": 110, "quantity": 3}
        result = calculate_plan(plan, self.settings, self.instrument, 0, 0, 0)
        self.assertEqual(result["status"], "REJECTED")

    def test_rejects_invalid_long_levels(self):
        plan = {"symbol": "BTCUSDT", "direction": "LONG", "entry_price": 100, "stop_loss": 105, "take_profit": 110, "quantity": 1}
        result = calculate_plan(plan, self.settings, self.instrument, 0, 0, 0)
        self.assertEqual(result["status"], "REJECTED")

    def test_daily_loss_limit_rejects_excess_exposure(self):
        plan = {"symbol": "BTCUSDT", "direction": "LONG", "entry_price": 100, "stop_loss": 95, "take_profit": 110, "quantity": 1}
        result = calculate_plan(plan, self.settings, self.instrument, 0, -296, 0)
        self.assertEqual(result["status"], "REJECTED")
        self.assertTrue(any("daily loss" in reason.lower() for reason in result["reasons"]))

    def test_maximum_positions_is_enforced(self):
        plan = {"symbol": "BTCUSDT", "direction": "LONG", "entry_price": 100, "stop_loss": 95, "take_profit": 110, "quantity": 1}
        result = calculate_plan(plan, self.settings, self.instrument, 3, 0, 0)
        self.assertEqual(result["status"], "REJECTED")

    def test_quantity_rounds_down_to_broker_step(self):
        self.assertEqual(floor_to_step(1.239, 0.01), 1.23)

    def test_short_plan_is_approved_with_correct_reward_risk(self):
        plan = {"symbol": "BTCUSDT", "direction": "SHORT", "entry_price": 100, "stop_loss": 105, "take_profit": 90, "quantity": 1}
        result = calculate_plan(plan, self.settings, self.instrument, 0, 0, 0)
        self.assertEqual(result["status"], "APPROVED")
        self.assertEqual(result["risk_reward"], 2)

    def test_rejects_non_finite_contract_multiplier_for_review(self):
        instrument = {**self.instrument, "contract_multiplier": float("nan")}
        plan = {"symbol": "BTCUSDT", "direction": "LONG", "entry_price": 100, "stop_loss": 95, "take_profit": 110, "quantity": 1}
        result = calculate_plan(plan, self.settings, instrument, 0, 0, 0)
        self.assertEqual(result["status"], "NEEDS_REVIEW")

    def test_rejects_non_finite_quantity_step(self):
        with self.assertRaises(ValueError):
            floor_to_step(1, float("inf"))

    def test_invalid_risk_settings_require_review(self):
        settings = {**self.settings, "account_equity": float("inf")}
        plan = {"symbol": "BTCUSDT", "direction": "LONG", "entry_price": 100, "stop_loss": 95, "take_profit": 110, "quantity": 1}
        result = calculate_plan(plan, settings, self.instrument, 0, 0, 0)
        self.assertEqual(result["status"], "NEEDS_REVIEW")


if __name__ == "__main__":
    unittest.main()
