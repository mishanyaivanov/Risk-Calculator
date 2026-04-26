import unittest

from main import historical_var_discrete, parametric_var
from riskcalc.bond_swap import (
    build_bond_cashflows,
    evaluate_bond_swap_package,
    solve_swap_spread_bps,
    value_bond_cashflows,
)
from riskcalc.option_pricing import black_scholes_price_and_greeks
from riskcalc.option_var import (
    covariance_from_sigmas_and_correlation,
    option_var_moment_approximations_multifactor,
    simulate_delta_gamma_pnl_multifactor,
)
from riskcalc.backtesting import (
    christoffersen_conditional_coverage_test,
    rolling_historical_var_es,
)
from riskcalc.risk_attribution import delta_normal_var_contributions
from riskcalc.stress_testing import evaluate_full_revaluation_stress_scenario


class RiskCalcExtensionsTest(unittest.TestCase):
    def test_confidence_validation_for_direct_api(self) -> None:
        with self.assertRaises(ValueError):
            historical_var_discrete([-1.0, 0.0, 1.0], 1.0)
        with self.assertRaises(ValueError):
            parametric_var([-1.0, 0.0, 1.0], 0.0)
        with self.assertRaises(ValueError):
            rolling_historical_var_es([float(i) for i in range(25)], 1.2, 20)

    def test_option_greeks_include_per_1pct_conventions(self) -> None:
        greeks = black_scholes_price_and_greeks(
            option_type="call",
            spot=100.0,
            strike=100.0,
            maturity_years=1.0,
            rate=0.05,
            volatility=0.2,
        )
        self.assertAlmostEqual(greeks["vega_per_1pct"], greeks["vega"] / 100.0)
        self.assertAlmostEqual(greeks["rho_per_1pct"], greeks["rho"] / 100.0)

    def test_covariance_validation_rejects_bad_correlation(self) -> None:
        with self.assertRaises(ValueError):
            covariance_from_sigmas_and_correlation(
                sigma_values=[0.1, 0.2],
                correlation_matrix=[[1.0, 1.2], [1.2, 1.0]],
            )
        with self.assertRaises(ValueError):
            covariance_from_sigmas_and_correlation(
                sigma_values=[0.1, 0.2],
                correlation_matrix=[[1.0, 0.5], [0.2, 1.0]],
            )

    def test_multifactor_delta_gamma_accepts_cross_gamma(self) -> None:
        result = option_var_moment_approximations_multifactor(
            delta_cash_values=[100.0, 50.0],
            gamma_cash_values=[10.0, 20.0],
            theta_horizon=0.0,
            mu_horizon_values=[0.0, 0.0],
            covariance_horizon=[[0.0004, 0.0001], [0.0001, 0.0009]],
            z_value=1.645,
            gamma_cross_matrix=[[10.0, 5.0], [5.0, 20.0]],
        )
        self.assertGreaterEqual(result["sigma_dg"], result["sigma_dn"])

        pnl = simulate_delta_gamma_pnl_multifactor(
            delta_cash_values=[0.0, 0.0],
            gamma_cash_values=[0.0, 0.0],
            theta_horizon=0.0,
            mean_vector=[1.0, 1.0],
            covariance_matrix=[[0.0, 0.0], [0.0, 0.0]],
            simulations=2,
            seed=1,
            gamma_cross_matrix=[[0.0, 2.0], [2.0, 0.0]],
        )
        self.assertEqual(pnl, [2.0, 2.0])

    def test_risk_attribution_matches_floored_var(self) -> None:
        result = delta_normal_var_contributions(
            factor_names=["A"],
            delta_cash_values=[100.0],
            mu_horizon_values=[1.0],
            covariance_horizon=[[0.0001]],
            z_value=1.645,
        )
        self.assertLess(result["portfolio_var_raw"], 0.0)
        self.assertEqual(result["portfolio_var"], 0.0)
        self.assertEqual(result["sum_component_var"], 0.0)

    def test_bond_cashflow_schedule(self) -> None:
        issue = {
            "issue_date": "2026-01-01",
            "maturity_date": "2027-01-01",
            "notional": 1_000_000.0,
            "coupon_rate": 0.12,
            "payment_frequency_months": 6,
        }
        cashflows = build_bond_cashflows(issue)

        self.assertEqual(len(cashflows), 2)
        self.assertGreater(cashflows[0]["coupon_cashflow"], 0.0)
        self.assertEqual(cashflows[0]["principal_cashflow"], 0.0)
        self.assertEqual(cashflows[-1]["principal_cashflow"], 1_000_000.0)

    def test_swap_spread_solves_coupon_target(self) -> None:
        issue = {
            "issue_date": "2026-01-01",
            "maturity_date": "2028-01-01",
            "notional": 1_000_000.0,
            "coupon_rate": 0.12,
            "payment_frequency_months": 6,
        }
        flat_curve = [
            {"tenor": "0D", "rate": 0.10},
            {"tenor": "1Y", "rate": 0.10},
            {"tenor": "2Y", "rate": 0.10},
        ]
        cashflows = build_bond_cashflows(issue)
        coupon_pv = value_bond_cashflows(
            cashflows,
            flat_curve,
            "2026-01-01",
            include_coupon=True,
            include_principal=False,
        )
        solved = solve_swap_spread_bps(
            cashflows,
            flat_curve,
            flat_curve,
            "2026-01-01",
            target_pv=coupon_pv["total_pv"],
            notional=1_000_000.0,
            hedge_ratio=1.0,
            pay_receive="pay",
        )

        self.assertAlmostEqual(solved["fair_spread_bps"], 200.0, places=6)
        self.assertAlmostEqual(solved["net_pv"], 0.0, places=6)

    def test_bond_swap_package_has_scenarios(self) -> None:
        result = evaluate_bond_swap_package(
            issue={
                "issue_date": "2026-01-01",
                "maturity_date": "2029-01-01",
                "notional": 1_000_000.0,
                "coupon_rate": 0.115,
                "payment_frequency_months": 6,
            },
            curve=[
                {"tenor": "0D", "rate": 0.09},
                {"tenor": "6M", "rate": 0.095},
                {"tenor": "1Y", "rate": 0.10},
                {"tenor": "3Y", "rate": 0.105},
            ],
            rate_scenarios_1y=[
                {"name": "lower", "rate_1y": 0.08},
                {"name": "base", "rate_1y": 0.10},
                {"name": "higher", "rate_1y": 0.12},
            ],
            hedge_ratios=(1.0, 0.5),
        )

        self.assertEqual(len(result["constructions"]), 3)
        self.assertEqual(len(result["constructions"][0]["scenarios"]), 3)
        self.assertIn("fair_spread_bps", result["constructions"][0])
        self.assertIn("coupon_plus_principal", result["bond_pv"])

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
