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
        result = calculate_plan(plan, self.settings, self.instrument, 0, -250, 0)
        self.assertEqual(result["status"], "REJECTED")
        self.assertTrue(any("daily loss" in reason.lower() for reason in result["reasons"]))

    def test_maximum_positions_is_enforced(self):
        plan = {"symbol": "BTCUSDT", "direction": "LONG", "entry_price": 100, "stop_loss": 95, "take_profit": 110, "quantity": 1}
        result = calculate_plan(plan, self.settings, self.instrument, 3, 0, 0)
        self.assertEqual(result["status"], "REJECTED")

    def test_quantity_rounds_down_to_broker_step(self):
        self.assertEqual(floor_to_step(1.239, 0.01), 1.23)


if __name__ == "__main__":
    unittest.main()
