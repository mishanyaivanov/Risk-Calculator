# Risk Analytics Platform: Architecture and Mathematical Engine Guide

## 1. Purpose

This project is a local web-based risk calculator built on top of FastAPI, Jinja templates, and a Python quantitative engine.

It contains two groups of functionality:

- Legacy functionality:
  - `1 Asset`
  - `Portfolio`
- New functionality:
  - `MOEX Market`
  - `Options`
  - `Futures & SPFI`
  - `Option Risk`
  - `Model Check`
  - `Factor Breakdown`
  - `Stress Scenarios`

The goal of the system is to provide a single local interface for:

- market data loading,
- basic VaR / ES analytics,
- portfolio risk,
- option pricing and Greeks,
- option VaR,
- linear derivative pricing and risk,
- backtesting,
- risk attribution,
- stress testing.

## 2. High-Level Architecture

The application is split into four logical layers.

### 2.1 Frontend Layer

File:

- `templates/index.html`

Responsibilities:

- renders all tabs in one page,
- collects user inputs,
- calls backend endpoints,
- formats results into cards, tables, and charts,
- supports workflow shortcuts from MOEX data into derivative forms.

Important note:

- legacy tabs `1 Asset` and `Portfolio` are preserved,
- new UX work is concentrated in the derivative and model-validation tabs.

### 2.2 API Layer

File:

- `main.py`

Responsibilities:

- defines request models with Pydantic,
- exposes FastAPI endpoints,
- converts frontend requests into service-layer calls,
- returns JSON results to the UI,
- serves the main HTML page.

### 2.3 Data Adapter Layer

Files:

- `services/tinkoff_service.py`
- `services/moex_service.py`

Responsibilities:

- fetch instruments and candles from Tinkoff,
- fetch instruments, option board data, and candles from MOEX,
- normalize external data into project-friendly dictionaries.

These modules are parsers/adapters, not pricing engines.

### 2.4 Mathematical Engine Layer

Files:

- `services/risk_calculator.py`
- `services/portfolio_manager.py`
- `services/option_pricing.py`
- `services/option_var.py`
- `services/forward_pricing.py`
- `services/linear_risk.py`
- `services/backtesting.py`
- `services/risk_attribution.py`
- `services/stress_testing.py`

Responsibilities:

- transform prices into PnL,
- compute VaR / ES,
- compute portfolio covariance risk,
- price options and compute Greeks,
- simulate option PnL,
- price futures / forwards / SPFI contracts,
- compute linear derivative risk,
- validate VaR / ES models,
- break portfolio VaR into factor contributions,
- run deterministic stress scenarios.

## 3. Runtime Flow

Typical runtime flow is:

1. The user opens the web page at `http://127.0.0.1:8000`.
2. The frontend collects user inputs.
3. The frontend calls an API endpoint in `main.py`.
4. `main.py` validates the request and forwards it to the proper service module.
5. The service module computes the result.
6. The API returns JSON.
7. The frontend renders formatted output.

For MOEX-assisted workflows the flow becomes:

1. Load instruments or option board from MOEX.
2. Select a row in the result table.
3. Push row data into `Options`, `Option Risk`, or `Futures & SPFI`.
4. Run pricing or risk calculations.

## 4. API Endpoints

### 4.1 Legacy Endpoints

- `GET /`
  - returns the main page.
- `GET /api/search`
  - Tinkoff instrument lookup.
- `POST /api/calculate`
  - single-asset VaR / ES / LVaR workflow.
- `POST /api/calculate_portfolio`
  - portfolio VaR and efficient frontier workflow.

### 4.2 New Endpoints

- `POST /api/backtest`
  - rolling VaR / ES backtesting and diagnostics.
- `POST /api/risk_attribution`
  - factor-based Delta-Normal VaR contributions.
- `POST /api/stress_test`
  - deterministic full revaluation stress scenarios for option portfolios.
- `GET /api/moex/instruments`
  - MOEX market instrument list.
- `GET /api/moex/option_board/{underlying_asset_code}`
  - MOEX option board for an underlying.
- `POST /api/moex/candles`
  - MOEX candles for a selected `SECID`.
- `POST /api/option_pricing`
  - Black-Scholes price and Greeks.
- `POST /api/option_var`
  - analytical and Monte Carlo option VaR.
- `POST /api/forward_pricing`
  - pricing for futures / forwards / SPFI.
- `POST /api/linear_var`
  - parametric / historical / scenario risk for linear derivatives.

## 5. Legacy Mathematical Functionality

### 5.1 `services/risk_calculator.py`

This is the original single-asset risk core.

Functions:

- `parse_price_input(raw_input)`
  - parses manual price strings into a list of floats.
- `generate_random_prices(days, start_price, volatility)`
  - creates a simulated price path for demo/testing.
- `normalize_confidence(value)`
  - converts confidence input into a supported decimal confidence.
- `z_value_for_confidence(confidence)`
  - returns the one-tailed normal quantile used in parametric VaR.
- `pnl_from_prices(prices, position_size)`
  - converts a price series into a monetary PnL series using simple price differences.
- `historical_var_discrete(pnl, confidence)`
  - discrete historical VaR from the left tail of the PnL distribution.
- `expected_shortfall_discrete(pnl, confidence)`
  - average loss in the tail beyond the VaR cutoff.
- `parametric_var(pnl, confidence)`
  - normal VaR using sample mean and standard deviation of PnL.
- `normal_liquidation_cost(mid_market_value, spread_percent)`
  - half-spread liquidation cost.
- `stressed_liquidation_cost(mid_market_value, spread_percent, confidence, sigma_spread_percent)`
  - stressed spread liquidation cost with a confidence-based spread shock.
- `linear_unwind_adjustment_factor(days)`
  - liquidation-horizon adjustment factor.
- `linear_unwind_adjusted_var(base_var, days)`
  - VaR adjusted for linear unwind across multiple days.

Core formulas:

- `PnL_t = position_size * (P_t - P_{t-1})`
- `VaR = max(0, -q_alpha(PnL))`
- `ES = max(0, -mean(tail PnL))`
- `Parametric q_alpha = mu - z * sigma`

### 5.2 `services/portfolio_manager.py`

This is the original portfolio risk block.

Functions:

- `calculate_portfolio_var(returns, weights, confidence, portfolio_value)`
  - variance-covariance portfolio VaR using the covariance matrix of returns.
- `generate_efficient_frontier(returns, num_portfolios)`
  - random portfolio generator for return/volatility visualization.

Core formulas:

- `sigma_p^2 = w^T Sigma w`
- `VaR = portfolio_value * z * sigma_p`

## 6. New Mathematical Functionality

### 6.1 `services/option_pricing.py`

This module provides the option pricing core.

Functions:

- `normalize_option_type(option_type)`
  - accepts `call/c` and `put/p`.
- `option_intrinsic_value(option_type, spot, strike)`
  - payoff at maturity.
- `black_scholes_price_and_greeks(option_type, spot, strike, maturity_years, rate, volatility, dividend_yield)`
  - Black-Scholes-Merton pricing and Greeks for European options.

Main formulas:

- `d1 = [ln(S/K) + (r - q + 0.5*sigma^2)T] / (sigma*sqrt(T))`
- `d2 = d1 - sigma*sqrt(T)`
- Call:
  - `C = S*e^(-qT)N(d1) - K*e^(-rT)N(d2)`
- Put:
  - `P = K*e^(-rT)N(-d2) - S*e^(-qT)N(-d1)`

Returned metrics:

- price,
- delta,
- gamma,
- vega,
- theta,
- rho,
- `d1`,
- `d2`.

### 6.2 `services/option_var.py`

This module provides analytical and simulation-based option risk.

Functions:

- `covariance_from_sigmas_and_correlation(sigma_values, correlation_matrix)`
  - builds a covariance matrix from volatilities and correlations.
- `option_var_moment_approximations(delta_cash, gamma_cash, theta_horizon, mu_horizon, sigma_horizon, z_value)`
  - single-factor Delta-Normal and Delta-Gamma approximations.
- `option_var_moment_approximations_multifactor(...)`
  - multifactor Delta-Normal and simplified Delta-Gamma approximations.
- `simulate_delta_gamma_pnl(delta_cash, gamma_cash, theta_horizon, mu_horizon, sigma_horizon, simulations, seed)`
  - Monte Carlo PnL for the single-factor Delta-Gamma approximation.
- `simulate_delta_gamma_pnl_multifactor(...)`
  - Monte Carlo PnL for multifactor Delta-Gamma.
- `simulate_full_revaluation_pnl(...)`
  - full repricing Monte Carlo for a single-factor option portfolio.
- `simulate_full_revaluation_pnl_multifactor(...)`
  - full repricing Monte Carlo for a multifactor option portfolio.

Risk logic:

- Delta-Normal approximates:
  - `PnL ≈ Delta_cash * dS + Theta`
- Delta-Gamma approximates:
  - `PnL ≈ Delta_cash * dS + 0.5 * Gamma_cash * dS^2 + Theta`
- Full Revaluation reprices the option after simulated shocks to:
  - spot,
  - implied volatility,
  - rate,
  - time-to-maturity.

Outputs used by the API:

- analytical VaR approximations,
- Monte Carlo PnL distribution,
- Monte Carlo VaR,
- Monte Carlo ES,
- optional full revaluation VaR / ES.

### 6.3 `services/forward_pricing.py`

This module prices linear derivatives.

Supported types:

- `futures`
- `forward`
- `spfi`

Functions:

- `normalize_linear_derivative_type(instrument_type)`
  - normalizes derivative type.
- `theoretical_forward_price(spot, maturity_years, rate, income_yield)`
  - carry-model fair price.
- `price_linear_derivative(instrument_type, spot, maturity_years, rate, income_yield, entry_price, quantity, multiplier, scenario_spot)`
  - fair price, carry, current value, PV, and scenario revaluation.

Core formulas:

- `F = S * exp((r - q) * T)`
- `discount_factor = exp(-rT)`
- `PnL_vs_entry = (F_current - F_entry) * quantity * multiplier`

This is the new pricing core for `Futures & SPFI`.

### 6.4 `services/linear_risk.py`

This module provides VaR / ES for linear derivatives.

Functions:

- `returns_from_prices(prices)`
  - converts historical prices into arithmetic returns.
- `rolling_horizon_pnl(single_day_pnl, horizon_days)`
  - aggregates daily PnL across a multi-day horizon.
- `linear_derivative_var(spot, quantity, multiplier, confidence, horizon_days, mu_daily, sigma_daily, historical_prices, scenario_move_pct, instrument_type)`
  - master function for linear derivative risk.

Capabilities:

- parametric VaR / ES from `mu_daily` and `sigma_daily`,
- historical VaR / ES from MOEX candle history,
- scenario PnL from a user-defined percentage move.

Core logic:

- cash exposure:
  - `exposure_cash = spot * quantity * multiplier`
- parametric horizon scaling:
  - `mu_horizon = mu_daily * horizon_days`
  - `sigma_horizon = sigma_daily * sqrt(horizon_days)`
- parametric PnL:
  - `PnL_mu = exposure_cash * mu_horizon`
  - `PnL_sigma = |exposure_cash| * sigma_horizon`

This is the new risk core for `Futures & SPFI`.

### 6.5 `services/backtesting.py`

This module validates VaR / ES models on rolling windows.

Functions:

- `_safe_log_probability(probability)`
  - clipping helper for likelihood calculations.
- `_chi2_sf_df1(statistic)`
  - chi-square survival function for 1 degree of freedom.
- `_chi2_sf_df2(statistic)`
  - chi-square survival function for 2 degrees of freedom.
- `rolling_historical_var_es(pnl, confidence, window)`
  - rolling historical VaR / ES backtest series.
- `kupiec_pof_test(exceptions, alpha)`
  - proportion-of-failures test.
- `christoffersen_independence_test(exceptions)`
  - independence test for exception clustering.
- `christoffersen_conditional_coverage_test(exceptions, alpha)`
  - combined coverage test.
- `es_realized_shortfall_diagnostics(realized_pnl, var_pnl_thresholds, es_losses)`
  - compares realized tail losses with predicted ES.

Outputs:

- rolling realized PnL,
- rolling VaR / ES thresholds,
- exception sequence,
- red/yellow/green test verdicts,
- ES tail-bias diagnostics.

### 6.6 `services/risk_attribution.py`

This module decomposes Delta-Normal portfolio VaR into factor contributions.

Functions:

- `_portfolio_sigma(exposures, covariance_matrix)`
  - portfolio volatility from exposures and covariance.
- `delta_normal_var_contributions(factor_names, delta_cash_values, mu_horizon_values, covariance_horizon, z_value)`
  - marginal and component VaR by factor.

Outputs:

- portfolio mean,
- portfolio sigma,
- portfolio VaR,
- marginal VaR by factor,
- component VaR by factor,
- percentage contribution share.

### 6.7 `services/stress_testing.py`

This module provides deterministic stress testing for option portfolios.

Functions:

- `evaluate_full_revaluation_stress_scenario(positions, horizon_days, underlying_return_shocks, volatility_shift, rate_shift)`
  - reprices each option position under a deterministic scenario.
- `build_standard_stress_scenarios(underlying_ids)`
  - returns standard built-in scenarios.

Built-in scenario families:

- market down 10%,
- market down 20%,
- crash plus volatility jump,
- rates up,
- rates down.

Outputs:

- base portfolio value,
- stressed portfolio value,
- total PnL,
- per-position stressed PnL.

## 7. Data Adapter Modules

### 7.1 `services/tinkoff_service.py`

Functions:

- `similarity_score(str1, str2, threshold)`
- `find_instruments(name, token)`
- `_price_to_float(price)`
- `get_candles(figi, start_date, end_date, token)`

Purpose:

- supports the legacy Tinkoff-based asset and portfolio workflows.

### 7.2 `services/moex_service.py`

Functions:

- `_rows_to_dicts(payload, table_name)`
- `_get_iss_json(session, url, params)`
- `_resolve_security_board(session, secid)`
- `get_market_instruments(session, engine, market)`
- `get_option_board(session, underlying_asset_code)`
- `get_instrument_candles(session, secid, start_date, end_date, engine, market)`

Purpose:

- supports the new MOEX-based derivative workflows,
- resolves `engine/market` automatically when missing,
- provides a bridge from MOEX selection to pricing/risk tabs.

## 8. Migration Status from `New functions`

The temporary directory `New functions` contains the teammate reference implementation.

Runtime-integrated modules already present in the main application:

- `New functions/backtesting.py` -> `services/backtesting.py`
- `New functions/risk_attribution.py` -> `services/risk_attribution.py`
- `New functions/stress_testing.py` -> `services/stress_testing.py`

Already integrated new derivative modules built on top of that layer:

- `services/option_pricing.py`
- `services/option_var.py`
- `services/forward_pricing.py`
- `services/linear_risk.py`
- `services/moex_service.py`

Reference-only files that remain in `New functions` and are not part of runtime web execution:

- `New functions/main.py`
- `New functions/README.md`
- `New functions/test_riskcalc_extensions.py`
- `New functions/__init__.py`

This means the important mathematical logic has been transferred into the working web service, while the temporary folder still acts as a source/reference snapshot.

## 9. Frontend Workflows

### 9.1 `1 Asset`

Use this tab for:

- Tinkoff-based single asset analysis,
- manual price sequences,
- random demo series,
- Historical VaR,
- ES,
- Parametric VaR,
- liquidation-aware metrics.

### 9.2 `Portfolio`

Use this tab for:

- multi-asset portfolio construction,
- covariance-based portfolio VaR,
- correlation matrix,
- efficient frontier visualization.

### 9.3 `MOEX Market`

Use this tab for:

- loading MOEX instrument lists,
- browsing option boards,
- downloading candles,
- sending selected rows into derivative workflows.

Recommended process:

1. Load instruments or option board.
2. Pick the relevant row.
3. Send it to `Options`, `Option Risk`, or `Futures & SPFI`.
4. If needed, load candles to fill spot and historical volatility inputs.

### 9.4 `Options`

Use this tab for:

- Black-Scholes pricing,
- Greeks for one option position,
- preparing a contract for risk analysis.

Recommended process:

1. Fill in option inputs manually or via `MOEX Market`.
2. Run pricing.
3. Review price and Greeks.
4. Send the contract to `Option Risk`.

### 9.5 `Option Risk`

Use this tab for:

- Delta-Normal VaR,
- Delta-Gamma VaR,
- Delta-Gamma Monte Carlo,
- Full Revaluation Monte Carlo.

Recommended process:

1. Start from `Options` or direct input.
2. Fill cash Greeks and horizon assumptions.
3. Run the risk calculation.
4. Compare analytical and simulation-based outputs.
5. Turn on full revaluation when you need a more realistic nonlinear result.

### 9.6 `Futures & SPFI`

Use this tab for:

- linear derivative pricing,
- fair value / carry analysis,
- present value vs entry price,
- scenario PnL,
- parametric and historical risk for futures / forwards / SPFI.

Recommended process:

1. Set spot, maturity, rate, carry inputs, quantity, and multiplier.
2. Run pricing.
3. In the risk section, either:
   - provide `mu_daily` and `sigma_daily`, or
   - load historical prices from MOEX candles.
4. Run linear risk.
5. Review VaR, ES, and scenario PnL.

### 9.7 `Model Check`

Use this tab for:

- rolling validation of VaR / ES models.

Recommended process:

1. Provide a historical PnL series.
2. Choose confidence and rolling window.
3. Run backtest.
4. Review:
   - exception frequency,
   - independence,
   - conditional coverage,
   - ES realized tail diagnostics.

### 9.8 `Factor Breakdown`

Use this tab for:

- factor-level Delta-Normal VaR decomposition.

Recommended process:

1. Prepare factor names.
2. Provide delta cash exposures.
3. Provide factor means and covariance matrix.
4. Run attribution.
5. Review marginal and component risk shares.

### 9.9 `Stress Scenarios`

Use this tab for:

- deterministic stress testing for option portfolios.

Recommended process:

1. Define option positions.
2. Define horizon and shocks.
3. Run the stress engine.
4. Compare built-in and custom scenarios.

## 10. Local Run Instructions

### 10.1 Docker

Use:

```bash
docker compose up --build
```

Then open:

```text
http://127.0.0.1:8000
```

### 10.2 Local Python

If dependencies are already installed, run:

```bash
python main.py
```

## 11. Operational Notes

- Confidence levels in the original single-asset logic are normalized to supported values.
- Option pricing assumes European Black-Scholes-Merton dynamics.
- Full revaluation risk includes optional shocks to volatility and rates.
- Linear derivative risk can work with either:
  - direct statistical inputs, or
  - historical prices.
- MOEX is now part of the live backend flow, not a disconnected experiment.

## 12. Current Scope and Limits

- The option engine is European-style only.
- The Delta-Gamma analytical formulas are approximations.
- Full revaluation Monte Carlo is more realistic, but also heavier.
- Some multifactor functions exist in the service layer even if the current UI mainly exposes the single-factor path.
- The temporary `New functions` directory is still present as a reference and should not be treated as the production runtime entrypoint.

## 13. Summary

The platform now combines:

- legacy VaR / portfolio analytics,
- new option pricing and option VaR,
- new futures / SPFI pricing and risk,
- MOEX-powered derivative data flow,
- model validation,
- factor attribution,
- stress testing.

The core design principle is:

- adapters fetch and normalize market data,
- API endpoints coordinate requests,
- service modules perform mathematical calculations,
- the frontend renders a simplified workflow for end users.

для поднятия: docker-compose up --build
http://0.0.0.0:8000/
