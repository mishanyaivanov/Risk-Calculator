import unittest

from riskcalc.backtesting import (
    christoffersen_conditional_coverage_test,
    rolling_historical_var_es,
)
from riskcalc.risk_attribution import delta_normal_var_contributions
from riskcalc.stress_testing import evaluate_full_revaluation_stress_scenario


class RiskCalcExtensionsTest(unittest.TestCase):
    def test_rolling_backtest_outputs(self) -> None:
        pnl = [
            1, -2, 3, -4, 5, -6, 2, 1, -3, 4, -1, 2, -2, 1, -1, 0, 2, -3, 1, 2,
            -2, 3, -4, 2, 1, -1, 2, -2, 1, 0, 2, -1, 1, -2, 3, -3, 2, 1, -1, 2,
            1, -2, 2, -1, 1, -2, 1, 2, -3, 1, 2, -1,
        ]
        result = rolling_historical_var_es(pnl, confidence=0.95, window=20)
        self.assertEqual(len(result["exceptions"]), len(pnl) - 20)
        self.assertEqual(len(result["realized_pnl"]), len(pnl) - 20)

        cc = christoffersen_conditional_coverage_test(result["exceptions"], alpha=0.05)
        self.assertIn(cc["verdict"], {"green", "yellow", "red"})
        self.assertGreaterEqual(float(cc["p_value"]), 0.0)
        self.assertLessEqual(float(cc["p_value"]), 1.0)

    def test_component_var_adds_up(self) -> None:
        result = delta_normal_var_contributions(
            factor_names=["U1", "U2"],
            delta_cash_values=[100000.0, -50000.0],
            mu_horizon_values=[0.001, 0.0005],
            covariance_horizon=[[0.0004, 0.0001], [0.0001, 0.0009]],
            z_value=1.645,
        )
        portfolio_var = float(result["portfolio_var"])
        sum_component = float(result["sum_component_var"])
        self.assertAlmostEqual(portfolio_var, sum_component, places=6)

    def test_stress_scenario_shapes(self) -> None:
        positions = [
            {
                "underlying_id": "U1",
                "option_type": "call",
                "spot": 100.0,
                "strike": 100.0,
                "maturity_years": 0.5,
                "rate": 0.05,
                "volatility": 0.2,
                "dividend_yield": 0.0,
                "quantity": 10.0,
                "multiplier": 1.0,
            }
        ]
        result = evaluate_full_revaluation_stress_scenario(
            positions=positions,
            horizon_days=10,
            underlying_return_shocks={"U1": -0.1},
            volatility_shift=0.05,
            rate_shift=0.0,
        )
        self.assertEqual(len(result["positions"]), 1)
        self.assertLess(float(result["total_pnl"]), 0.0)


if __name__ == "__main__":
    unittest.main()
