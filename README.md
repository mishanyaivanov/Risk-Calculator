# Risk-Calculator Core

Quantitative backend core for a course-project risk calculator. The repository contains reusable calculation modules for market risk, option risk, backtesting, stress testing, risk attribution, and bond/swap analysis. It is intentionally built as a Python calculation engine, not as a web application.

The frontend team can wrap these modules in REST endpoints, forms, dashboards, or reports without duplicating quantitative logic.

Current working branch: `Misha`

## Table Of Contents

- [Purpose](#purpose)
- [Current Scope](#current-scope)
- [Repository Structure](#repository-structure)
- [Quick Start](#quick-start)
- [Testing](#testing)
- [Integration Principles](#integration-principles)
- [Data And Sign Conventions](#data-and-sign-conventions)
- [Core Modules](#core-modules)
- [Stable Programmatic Contracts](#stable-programmatic-contracts)
- [Examples](#examples)
- [Model Validation Notes](#model-validation-notes)
- [Limitations](#limitations)
- [Recommended Frontend/API Adapter](#recommended-frontendapi-adapter)
- [Development Checklist](#development-checklist)

## Purpose

The project solves two related tasks:

1. Provide a clean quantitative core for risk calculations.
2. Expose predictable Python contracts that can later be embedded into a website or service layer.

The codebase should be treated as the source of truth for calculations. UI code should normalize user input, call these functions, and render the returned dictionaries.

## Current Scope

Implemented model families:

- Historical VaR and Expected Shortfall.
- Parametric normal VaR.
- Liquidity-adjusted VaR.
- Linear unwind adjustment for liquidation periods.
- Black-Scholes-Merton pricing and Greeks.
- Option VaR:
  - Delta-Normal.
  - Delta-Gamma moment matching.
  - Delta-Gamma Monte Carlo.
  - Full Revaluation Monte Carlo.
  - Single-factor and multifactor variants.
  - Full gamma matrix support for multifactor Delta-Gamma.
- Rolling VaR/ES backtesting:
  - Kupiec POF.
  - Christoffersen independence.
  - Christoffersen conditional coverage.
  - ES realized shortfall diagnostics.
- Deterministic option stress testing.
- Delta-normal risk attribution:
  - marginal VaR;
  - component VaR;
  - component shares.
- Bond issue plus interest-rate swap spread selection:
  - bond cashflow schedule;
  - curve interpolation;
  - fair spread selection for a floating swap leg;
  - hedge-ratio variants;
  - one-year rate scenario analysis.

## Repository Structure

```text
Risk-Calculator/
├── main.py
├── README.md
├── riskcalc/
│   ├── __init__.py
│   ├── backtesting.py
│   ├── bond_swap.py
│   ├── option_pricing.py
│   ├── option_var.py
│   ├── risk_attribution.py
│   └── stress_testing.py
└── tests/
    └── test_riskcalc_extensions.py
```

Module responsibilities:

- `main.py`: CLI entry point and orchestration helpers for P&L, VaR, ES, LVaR, option portfolio workflows, and interactive scenarios.
- `riskcalc/option_pricing.py`: Black-Scholes-Merton pricing, Greeks, intrinsic value, option type normalization.
- `riskcalc/option_var.py`: Delta-Normal, Delta-Gamma, Monte Carlo simulation, full revaluation option VaR, covariance/correlation validation.
- `riskcalc/backtesting.py`: rolling VaR/ES backtesting and statistical coverage tests.
- `riskcalc/risk_attribution.py`: marginal and component VaR decomposition.
- `riskcalc/stress_testing.py`: deterministic full-revaluation stress scenarios for option portfolios.
- `riskcalc/bond_swap.py`: bond cashflows, curve interpolation, swap spread calibration, and one-year rate scenario analysis.
- `tests/test_riskcalc_extensions.py`: regression and sanity tests for the extended calculation engine.

## Quick Start

Requirements:

- Python 3.10+
- No mandatory third-party Python dependencies for the current core.

Run from the project root:

```bash
cd /Users/ivanovmichael/Documents/Risk-Calculator
python3 main.py
```

Run all tests:

```bash
python3 -m unittest discover -s tests -p "test_*.py"
```

Compile-check Python modules:

```bash
python3 -m py_compile main.py riskcalc/*.py
```

## Testing

The current test suite covers:

- rolling VaR/ES backtest output shapes;
- Christoffersen conditional coverage result shape;
- component VaR add-up behavior;
- stress scenario revaluation;
- bond cashflow schedule generation;
- bond/swap fair spread calibration;
- bond/swap scenario output shape;
- direct confidence validation;
- Greek `per 1pct` conventions;
- invalid correlation/covariance rejection;
- full gamma matrix support;
- risk attribution floor behavior.

Expected result:

```text
Ran 11 tests
OK
```

Recommended pre-integration check:

```bash
python3 -m py_compile main.py riskcalc/*.py
python3 -m unittest discover -s tests -p "test_*.py"
```

## Integration Principles

The core is designed around stable Python functions and JSON-compatible dictionaries.

Frontend/API layer should:

- parse form fields;
- normalize percentages to decimals;
- validate required fields;
- call `riskcalc` functions;
- serialize results to JSON;
- display warnings and model notes returned by the core.

Frontend/API layer should not:

- duplicate quantitative formulas;
- silently coerce unsupported confidence levels;
- hide validation errors;
- reinterpret signs without an explicit adapter convention.

## Data And Sign Conventions

General:

- Percent values inside the core are decimals.
- `5%` is represented as `0.05`.
- `100 bps` is represented as `0.01`.
- P&L values follow the convention `P&L < 0` means loss.
- VaR and ES are returned as positive loss magnitudes.

Option values:

- `quantity > 0` means long option exposure.
- `quantity < 0` means short option exposure.
- `multiplier` scales one contract into economic exposure.
- Portfolio value is `price * quantity * multiplier`.

Greeks:

- `delta`, `gamma`, `vega`, `theta`, and `rho` follow standard Black-Scholes-Merton conventions.
- `vega` is value sensitivity to a `1.0` volatility move.
- `rho` is value sensitivity to a `1.0` rate move.
- `vega_per_1pct` is sensitivity to a 1 percentage point volatility move.
- `rho_per_1pct` is sensitivity to a 1 percentage point rate move.
- `delta_cash = delta * spot * quantity * multiplier`.
- `gamma_cash = gamma * spot^2 * quantity * multiplier`.

Backtesting:

- Exceptions are detected when realized P&L is strictly below the VaR P&L threshold.
- Example: if `var_pnl_threshold = -100`, then `realized_pnl = -120` is an exception.

Bond/swap:

- Bond target PV is positive.
- A pay-floating swap leg is negative.
- Spread calibration solves `target_pv + swap_pv = target_net_pv`.
- Default `target_net_pv` is `0`.

## Core Modules

### `main.py`

Useful non-interactive helpers:

- `pnl_from_prices(prices, position_size=1.0)`
- `pnl_from_returns(returns, position_value, returns_in_percent)`
- `aggregate_pnl_series(series_list)`
- `historical_var_discrete(pnl, confidence)`
- `expected_shortfall_discrete(pnl, confidence)`
- `parametric_var(pnl, confidence)`
- `normal_liquidation_cost(mid_market_value, spread_percent)`
- `stressed_liquidation_cost(mid_market_value, spread_percent, confidence, sigma_spread_percent)`
- `linear_unwind_adjusted_var(base_var, days)`
- `evaluate_option_position(position)`
- `aggregate_option_results(evaluated_positions)`
- `aggregate_cash_exposures_by_underlying(evaluated_positions)`

Supported CLI confidence levels:

- `0.95`
- `0.99`

Direct helper functions validate that confidence is inside `(0, 1)`.

### `riskcalc.option_pricing`

Primary function:

```python
black_scholes_price_and_greeks(
    option_type: str,
    spot: float,
    strike: float,
    maturity_years: float,
    rate: float,
    volatility: float,
    dividend_yield: float = 0.0,
) -> dict[str, float]
```

Returned fields:

- `d1`
- `d2`
- `price`
- `delta`
- `gamma`
- `vega`
- `vega_per_1pct`
- `theta`
- `rho`
- `rho_per_1pct`

Validation:

- `spot > 0`
- `strike > 0`
- `maturity_years > 0`
- `volatility > 0`
- option type must be call/put or accepted aliases.

### `riskcalc.option_var`

Key functions:

- `covariance_from_sigmas_and_correlation(sigma_values, correlation_matrix)`
- `option_var_moment_approximations(...)`
- `option_var_moment_approximations_multifactor(...)`
- `simulate_delta_gamma_pnl(...)`
- `simulate_delta_gamma_pnl_multifactor(...)`
- `simulate_full_revaluation_pnl(...)`
- `simulate_full_revaluation_pnl_multifactor(...)`

Validation added for covariance/correlation inputs:

- matrix must be square;
- correlation matrix must be symmetric;
- correlation values must be in `[-1, 1]`;
- correlation diagonal must be `1`;
- covariance matrix must be symmetric;
- covariance diagonal must be non-negative;
- covariance matrix must be PSD.

Multifactor Delta-Gamma supports two modes.

Backward-compatible diagonal gamma mode:

```python
option_var_moment_approximations_multifactor(
    delta_cash_values=[100000.0, -50000.0],
    gamma_cash_values=[12000.0, 8000.0],
    theta_horizon=-100.0,
    mu_horizon_values=[0.0, 0.0],
    covariance_horizon=[[0.0004, 0.0001], [0.0001, 0.0009]],
    z_value=1.645,
)
```

Full gamma matrix mode:

```python
option_var_moment_approximations_multifactor(
    delta_cash_values=[100000.0, -50000.0],
    gamma_cash_values=[12000.0, 8000.0],
    theta_horizon=-100.0,
    mu_horizon_values=[0.0, 0.0],
    covariance_horizon=[[0.0004, 0.0001], [0.0001, 0.0009]],
    z_value=1.645,
    gamma_cross_matrix=[
        [12000.0, 1500.0],
        [1500.0, 8000.0],
    ],
)
```

If `gamma_cross_matrix` is omitted, the module preserves the previous diagonal-gamma behavior.

### `riskcalc.backtesting`

Primary function:

```python
rolling_historical_var_es(
    pnl: list[float],
    confidence: float,
    window: int,
) -> dict[str, list[float] | list[bool]]
```

Returned fields:

- `realized_pnl`
- `var_losses`
- `var_pnl_thresholds`
- `es_losses`
- `es_pnl_values`
- `exceptions`

Statistical tests:

- `kupiec_pof_test(exceptions, alpha)`
- `christoffersen_independence_test(exceptions)`
- `christoffersen_conditional_coverage_test(exceptions, alpha)`
- `es_realized_shortfall_diagnostics(realized_pnl, var_pnl_thresholds, es_losses)`

Verdict scale:

- `green`: no statistical warning at configured levels;
- `yellow`: warning region;
- `red`: failed coverage/independence region.

### `riskcalc.risk_attribution`

Primary function:

```python
delta_normal_var_contributions(
    factor_names: list[str],
    delta_cash_values: list[float],
    mu_horizon_values: list[float],
    covariance_horizon: list[list[float]],
    z_value: float,
) -> dict
```

Returned fields:

- `portfolio_mu`
- `portfolio_sigma`
- `portfolio_var_raw`
- `portfolio_var`
- `sum_component_var`
- `rows`

Each row contains:

- `factor`
- `delta_cash`
- `mu_horizon`
- `marginal_var`
- `component_var`
- `component_share_pct`

Important behavior:

- `portfolio_var_raw` is calculated before floor-at-zero.
- `portfolio_var` is floored at zero.
- If raw VaR is negative, component VaR is also floored consistently to avoid negative component decomposition for zero portfolio VaR.

### `riskcalc.stress_testing`

Primary function:

```python
evaluate_full_revaluation_stress_scenario(
    positions: list[dict[str, float | str]],
    horizon_days: int,
    underlying_return_shocks: dict[str, float],
    volatility_shift: float = 0.0,
    rate_shift: float = 0.0,
) -> dict
```

Returned fields:

- `base_value`
- `stressed_value`
- `total_pnl`
- `positions`

Standard scenario helper:

```python
build_standard_stress_scenarios(underlying_ids)
```

Built-in scenarios:

- `Market -10%`
- `Market -20%`
- `Crash -15% + Vol +10pp`
- `Rates +100 bps`
- `Rates -100 bps`

### `riskcalc.bond_swap`

Primary high-level function:

```python
evaluate_bond_swap_package(
    issue,
    curve,
    valuation_date=None,
    rate_scenarios_1y=None,
    hedge_ratios=(1.0, 0.75, 0.5),
    include_full_issue_variant=True,
) -> dict
```

Purpose:

- Build bond cashflows.
- Present-value coupon and principal components.
- Calibrate fair spread in bps for a pay-floating swap leg.
- Generate construction variants.
- Revalue each construction under one-year rate scenarios.

Supported issue fields:

```python
{
    "issue_date": "2026-01-01",
    "maturity_date": "2029-01-01",
    "notional": 1_000_000_000,
    "coupon_rate": 0.115,
    "payment_frequency_months": 6,
    "day_count": "ACT/365",
}
```

Supported curve point formats:

```python
{"tenor": "6M", "rate": 0.095}
{"tenor_years": 0.5, "rate": 0.095}
("1Y", 0.10)
(1.0, 0.10)
```

Supported tenor suffixes:

- `D`: days;
- `W`: weeks;
- `M`: months;
- `Y`: years;
- `0D`, `ON`, `O/N`, `TODAY` for zero tenor.

Output structure:

- `issue`
- `valuation_date`
- `curve`
- `cashflows`
- `bond_pv`
- `constructions`
- `model_notes`
- `warnings`

Construction output:

- `name`
- `description`
- `target_type`
- `hedge_ratio`
- `fair_spread_bps`
- `target_pv`
- `swap_pv`
- `net_pv`
- `pv_change_per_1bp`
- `scenario_date`
- `scenarios`

Default construction variants:

- `coupon_hedge_100pct`
- `coupon_hedge_75pct`
- `coupon_hedge_50pct`
- `full_issue_hedge_100pct`

The `full_issue_hedge_100pct` variant is intentionally marked as Excel-style. It attempts to offset coupon plus principal PV using a floating leg and can generate a very large spread. The module returns warnings when this looks economically aggressive.

## Stable Programmatic Contracts

### Option Position Input

```python
{
    "underlying_id": "U1",
    "option_type": "call",
    "spot": 100.0,
    "strike": 100.0,
    "maturity_years": 0.5,
    "rate": 0.05,
    "volatility": 0.2,
    "dividend_yield": 0.0,
    "quantity": 1.0,
    "multiplier": 1.0,
}
```

### Stress Scenario Input

```python
{
    "name": "Crash -15% + Vol +10pp",
    "underlying_shocks": {"U1": -0.15, "U2": -0.15},
    "volatility_shift": 0.10,
    "rate_shift": 0.00,
}
```

### Bond/Swap Input

```python
{
    "issue": {
        "issue_date": "2026-01-01",
        "maturity_date": "2029-01-01",
        "notional": 1_000_000_000,
        "coupon_rate": 0.115,
        "payment_frequency_months": 6,
    },
    "curve": [
        {"tenor": "0D", "rate": 0.09},
        {"tenor": "6M", "rate": 0.095},
        {"tenor": "1Y", "rate": 0.10},
        {"tenor": "3Y", "rate": 0.105},
    ],
    "rate_scenarios_1y": [
        {"name": "rates_down", "rate_1y": 0.08},
        {"name": "base", "rate_1y": 0.10},
        {"name": "rates_up", "rate_1y": 0.12},
    ],
}
```

## Examples

### Basic Historical VaR And ES

```python
from main import pnl_from_prices, historical_var_discrete, expected_shortfall_discrete

prices = [100, 101, 99, 98, 102, 101]
pnl = pnl_from_prices(prices, position_size=1.0)

var_loss, var_pnl, var_order_stat = historical_var_discrete(pnl, 0.95)
es_loss, es_pnl, tail_count = expected_shortfall_discrete(pnl, 0.95)

print(var_loss, es_loss)
```

### Black-Scholes Pricing

```python
from riskcalc.option_pricing import black_scholes_price_and_greeks

result = black_scholes_price_and_greeks(
    option_type="call",
    spot=100.0,
    strike=100.0,
    maturity_years=1.0,
    rate=0.05,
    volatility=0.20,
)

print(result["price"])
print(result["delta"])
print(result["vega_per_1pct"])
```

### Rolling Backtest

```python
from riskcalc.backtesting import (
    rolling_historical_var_es,
    christoffersen_conditional_coverage_test,
)

pnl = [
    -1, 2, -2, 1, -1, 3, -2, 1, -1, 2,
    -2, 1, -1, 2, -3, 1, 2, -1, 1, -2, 2,
]

history = rolling_historical_var_es(pnl=pnl, confidence=0.95, window=20)
cc = christoffersen_conditional_coverage_test(history["exceptions"], alpha=0.05)

print(cc["verdict"])
```

### Bond/Swap Package

```python
from riskcalc.bond_swap import evaluate_bond_swap_package

result = evaluate_bond_swap_package(
    issue={
        "issue_date": "2026-01-01",
        "maturity_date": "2029-01-01",
        "notional": 1_000_000_000,
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
        {"name": "rates_down", "rate_1y": 0.08},
        {"name": "base", "rate_1y": 0.10},
        {"name": "rates_up", "rate_1y": 0.12},
    ],
)

for construction in result["constructions"]:
    print(construction["name"], construction["fair_spread_bps"])
```

Expected sanity behavior for the example above:

- `coupon_hedge_100pct` fair spread is around `140 bps`.
- calibrated `net_pv` is close to `0`.
- `full_issue_hedge_100pct` may return a warning because principal is included in the hedge target.

## Model Validation Notes

The following sanity checks have been used during development:

- Black-Scholes-Merton call/put benchmark:
  - `S=100`, `K=100`, `T=1`, `r=5%`, `sigma=20%`;
  - call price around `10.450584`;
  - put price around `5.573526`;
  - put-call parity error close to `0`.
- Historical VaR/ES order-statistic checks on small deterministic P&L samples.
- Delta-Gamma deterministic simulation checks when volatility is zero.
- Risk attribution add-up checks for normal risk settings.
- Covariance validation checks for invalid correlations and non-symmetric matrices.
- Bond/swap fair spread checks on flat curves.

## Limitations

This is a course-project quant core, not a production trading or regulatory risk engine.

Known limitations:

- No REST API layer is included yet.
- CLI confidence presets are limited to `95%` and `99%`.
- Historical VaR uses a discrete order statistic without interpolation.
- Parametric VaR assumes normal P&L.
- Option pricing uses European Black-Scholes-Merton assumptions.
- The full revaluation option model assumes simulated return shocks and additive vol/rate shocks.
- Backtesting uses simplified traffic-light style verdicts.
- Bond/swap uses ACT/365 and annual compounding.
- Bond/swap scenario curves are built with a simple 1Y-pivot shift, not a full market term-structure model.
- No holiday calendars, business-day adjustments, fixing schedules, collateral/OIS discounting, or day-count convention library is implemented.

These limitations are acceptable for the current educational scope, but they should be visible in the frontend if the UI presents results to non-technical users.

## Recommended Frontend/API Adapter

A thin adapter layer should be added outside the quant modules.

Recommended adapter responsibilities:

1. Receive JSON from the frontend.
2. Validate required fields.
3. Normalize:
   - percentages to decimals;
   - dates to ISO strings;
   - empty optional fields to defaults;
   - numeric strings to floats;
   - confidence inputs to supported values.
4. Call core functions.
5. Catch `ValueError` and return user-readable API errors.
6. Return a stable JSON response.

Suggested response envelope:

```python
{
    "ok": True,
    "result": {...},
    "warnings": [],
    "model_notes": [],
}
```

Suggested error envelope:

```python
{
    "ok": False,
    "error": {
        "code": "VALIDATION_ERROR",
        "message": "confidence должен быть в диапазоне (0, 1).",
        "field": "confidence",
    },
}
```

Frontend display recommendations:

- Show VaR/ES as positive loss amounts.
- Keep P&L sign visible in charts.
- Label `vega_per_1pct` and `rho_per_1pct` instead of raw `vega`/`rho` for beginner users.
- Show `warnings` from `bond_swap` prominently.
- Show `model_notes` in an expandable explanation block.
- Do not expose raw JSON in beginner mode.
- Do not silently replace unsupported confidence values.

## Development Checklist

Before changing calculation logic:

```bash
pwd
git branch --show-current
git status --short
rg --files
```

Before handing changes to frontend:

```bash
python3 -m py_compile main.py riskcalc/*.py
python3 -m unittest discover -s tests -p "test_*.py"
```

When adding or changing a model:

- keep existing public function names unless a breaking change is explicitly approved;
- add new fields instead of renaming old fields;
- document sign conventions;
- document units and scaling;
- add at least one deterministic unit test;
- add one sanity-check example to this README if the feature is user-facing;
- keep returned objects JSON-compatible.

## Project Status

The current codebase is suitable as a backend calculation core for the course project. It is structured enough for frontend integration, and the main remaining engineering step is to add a thin service/API layer that wraps the functions documented above.
