# Risk Analytics Platform

## 1. Purpose

This project is a local web-based risk calculator built with:

- FastAPI backend
- Jinja single-page frontend
- Python mathematical engine
- Tinkoff and MOEX market-data adapters
- Docker-based local runtime

The application combines legacy portfolio-risk functionality with new derivative workflows.

It is designed for:

- single-asset risk estimation
- portfolio risk estimation
- option pricing and Greeks
- option VaR and Monte Carlo simulation
- futures / forward / SPFI pricing
- linear derivative VaR / ES
- model backtesting
- factor risk attribution
- deterministic stress testing

## 2. Runtime Architecture

The application has four layers.

### 2.1 Frontend Layer

Primary file:

- `templates/index.html`

Responsibilities:

- render the whole workspace in one page
- switch between `Novice` and `Pro` modes
- collect form inputs
- call backend endpoints
- show cards, tables, charts, and inline errors
- hide raw JSON in novice mode

### 2.2 API Layer

Primary file:

- `main.py`

Responsibilities:

- define request schemas
- validate incoming data
- call service-layer functions
- normalize API responses for the UI
- serve the main HTML page

### 2.3 Data Adapter Layer

Files:

- `services/tinkoff_service.py`
- `services/moex_service.py`

Responsibilities:

- fetch instruments and candles from external providers
- convert external responses into project-friendly dictionaries
- feed pricing and risk tabs with market data

Important note:

- these modules are data adapters, not pricing engines

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

- transform prices into PnL
- compute VaR / ES / LVaR
- compute portfolio covariance risk
- price derivatives
- simulate nonlinear PnL
- decompose risk by factor
- validate models on history
- reprice portfolios under stress scenarios

## 3. UI Modes

The interface supports two experience modes.

### 3.1 Novice Mode

Visible tabs:

- `One Asset`
- `Portfolio`
- `MOEX`
- `Stress Scenarios`

Design goals:

- no raw JSON in the main path
- plain-language metric labels
- preset-based inputs
- inline validation and clear next-step messages
- inline field explanations directly in the UI

### 3.2 Pro Mode

Visible tabs:

- all novice tabs
- `Options`
- `Futures & SPFI`
- `Option Risk`
- `Model Check`
- `Factor Breakdown`

Design goals:

- full analytical coverage
- advanced controls
- optional raw details through collapsible sections
- structured builders instead of raw JSON where the workflow can be simplified

## 4. Role of MOEX API

MOEX is used as a live market-data source for the new derivative workflows.

It is **not** used as the pricing engine.

What MOEX provides in this project:

- market instrument lists
- option board rows
- historical candles by `SECID`
- auto-filled spot values
- auto-filled historical `mu` and `sigma`
- workflow shortcuts from market data into derivative forms

What MOEX does not provide here:

- Greeks
- VaR
- ES
- pricing logic
- stress logic

Those calculations are performed locally in the Python mathematical engine.

## 5. Full Feature Map

### 5.1 Legacy Functionality

- `One Asset`
- `Portfolio`

### 5.2 New Functionality

- `MOEX`
- `Options`
- `Futures & SPFI`
- `Option Risk`
- `Model Check`
- `Factor Breakdown`
- `Stress Scenarios`

### 5.3 Migration Status from `New functions`

The temporary directory `New functions` was used as a teammate reference source.

Integrated into runtime:

- `New functions/backtesting.py` -> `services/backtesting.py`
- `New functions/risk_attribution.py` -> `services/risk_attribution.py`
- `New functions/stress_testing.py` -> `services/stress_testing.py`

Added on top of that integrated layer:

- `services/option_pricing.py`
- `services/option_var.py`
- `services/forward_pricing.py`
- `services/linear_risk.py`
- `services/moex_service.py`

Reference-only files that remain outside runtime:

- `New functions/main.py`
- `New functions/README.md`
- `New functions/test_riskcalc_extensions.py`
- `New functions/__init__.py`

## 6. API Endpoints

### 6.1 Core Endpoints

- `GET /`
  - serves the UI
- `GET /api/search`
  - Tinkoff instrument search
- `POST /api/calculate`
  - single-asset VaR / ES / LVaR
- `POST /api/calculate_portfolio`
  - portfolio VaR and efficient frontier

### 6.2 Derivative and Validation Endpoints

- `GET /api/moex/instruments`
  - MOEX instrument list
- `GET /api/moex/option_board/{underlying_asset_code}`
  - MOEX option board
- `POST /api/moex/candles`
  - MOEX candles
- `POST /api/option_pricing`
  - Black-Scholes price and Greeks
- `POST /api/option_var`
  - analytical option VaR and Monte Carlo
- `POST /api/forward_pricing`
  - futures / forward / SPFI pricing
- `POST /api/linear_var`
  - linear derivative VaR / ES / scenario PnL
- `POST /api/backtest`
  - rolling backtest and diagnostics
- `POST /api/risk_attribution`
  - factor VaR attribution
- `POST /api/stress_test`
  - full-revaluation stress scenarios

## 7. Frontend Contract Sheet

This section documents the most important API-to-UI contracts.

### 7.1 `POST /api/calculate`

Purpose:

- single-asset risk calculation

Important response fields:

- `historical_var`
- `es`
- `parametric_var`
- `lvar`
- `risk_status`
- `candles`
- `pnl_series`

Important UX rule:

- the single-asset screen no longer shows pseudo-backtest output
- it shows `risk_status` instead

`risk_status` contract:

- `severity`: `green | yellow | red`
- `label`: plain-language risk label
- `loss_share_pct`: VaR as percent of position value
- `summary`: short guidance text

### 7.2 `POST /api/calculate_portfolio`

Purpose:

- portfolio risk and efficient frontier

Important response fields:

- `portfolio_metrics`
- `correlation_matrix`
- `dates`
- `assets_cumulative_returns`
- `portfolio_cumulative_return`
- `efficient_frontier`

Validation rules:

- portfolio weights must sum to a positive value
- live Tinkoff data requires `TINKOFF_TOKEN`

### 7.3 `POST /api/option_var`

Purpose:

- option risk analytics

Important response fields:

- `approximations`
- `pnl_dg_mc`
- `mc_var`
- `mc_es`
- `seed_used`
- `seed_mode`
- `full_revaluation`

Monte Carlo contract:

- `seed` in the request is optional
- if `seed` is omitted, the backend uses a random seed
- if `seed` is provided, the result is reproducible

UI behavior:

- novice users do not see this tab
- pro users can choose random or fixed-seed mode

### 7.4 Error Handling Contract

UI rule for all tabs:

- every request checks `res.ok`
- errors are taken from `detail` first, then `error`
- errors are shown inline inside the current tab
- stale success output is not treated as a valid new result

## 8. Mathematical Engine: Legacy Functions

## 8.1 `services/risk_calculator.py`

This is the original single-asset risk core.

Functions:

- `parse_price_input(raw_input)`
  - parse manual text input into numeric prices
- `generate_random_prices(days, start_price, volatility)`
  - generate a demo price path
- `normalize_confidence(value)`
  - normalize confidence from decimal or percent form
- `z_value_for_confidence(confidence)`
  - compute the normal quantile for any valid confidence in `(0, 1)`
- `pnl_from_prices(prices, position_size)`
  - convert price history into PnL series
- `historical_var_discrete(pnl, confidence)`
  - historical discrete VaR
- `expected_shortfall_discrete(pnl, confidence)`
  - historical ES
- `parametric_var(pnl, confidence)`
  - normal VaR using sample mean and volatility
- `normal_liquidation_cost(mid_market_value, spread_percent)`
  - basic liquidation cost
- `stressed_liquidation_cost(mid_market_value, spread_percent, confidence, sigma_spread_percent)`
  - stressed liquidation cost
- `linear_unwind_adjustment_factor(days)`
  - multi-day unwind factor
- `linear_unwind_adjusted_var(base_var, days)`
  - LVaR-style unwind adjustment

Main formulas:

- `PnL_t = position_size * (P_t - P_(t-1))`
- `VaR = max(0, -q_alpha(PnL))`
- `ES = max(0, -average(tail PnL))`
- `q_alpha = mu - z * sigma`

## 8.2 `services/portfolio_manager.py`

This is the original portfolio-risk block.

Functions:

- `calculate_portfolio_var(returns, weights, confidence, portfolio_value)`
  - covariance-based portfolio VaR
- `generate_efficient_frontier(returns, num_portfolios)`
  - random portfolio cloud for return-risk visualization

Main formulas:

- `sigma_p^2 = w^T Sigma w`
- `VaR = portfolio_value * z * sigma_p`

## 9. Mathematical Engine: New Functions

## 9.1 `services/option_pricing.py`

Purpose:

- price a European option and compute Greeks

Functions:

- `normalize_option_type(option_type)`
- `option_intrinsic_value(option_type, spot, strike)`
- `black_scholes_price_and_greeks(option_type, spot, strike, maturity_years, rate, volatility, dividend_yield)`

Main formulas:

- `d1 = [ln(S/K) + (r - q + 0.5*sigma^2)T] / (sigma*sqrt(T))`
- `d2 = d1 - sigma*sqrt(T)`
- `Call = S*exp(-qT)*N(d1) - K*exp(-rT)*N(d2)`
- `Put = K*exp(-rT)*N(-d2) - S*exp(-qT)*N(-d1)`

Returned metrics:

- price
- delta
- gamma
- vega
- theta
- rho
- `d1`
- `d2`

## 9.2 `services/option_var.py`

Purpose:

- estimate option VaR by approximation and simulation

Functions:

- `covariance_from_sigmas_and_correlation(sigma_values, correlation_matrix)`
- `option_var_moment_approximations(delta_cash, gamma_cash, theta_horizon, mu_horizon, sigma_horizon, z_value)`
- `option_var_moment_approximations_multifactor(...)`
- `simulate_delta_gamma_pnl(delta_cash, gamma_cash, theta_horizon, mu_horizon, sigma_horizon, simulations, seed)`
- `simulate_delta_gamma_pnl_multifactor(...)`
- `simulate_full_revaluation_pnl(...)`
- `simulate_full_revaluation_pnl_multifactor(...)`

Single-factor approximation logic:

- `PnL ~= Delta_cash * dS + Theta`
- `PnL ~= Delta_cash * dS + 0.5 * Gamma_cash * dS^2 + Theta`

Simulation logic:

- Delta-Gamma Monte Carlo simulates spot shocks and applies the Delta-Gamma approximation
- Full Revaluation Monte Carlo simulates shocks and reprices the option with the pricing engine

Current runtime behavior:

- Monte Carlo is random by default
- fixed seed is optional
- backend returns `seed_used`

## 9.3 `services/forward_pricing.py`

Purpose:

- price linear derivatives such as futures, forwards, and SPFI-style contracts

Functions:

- `normalize_linear_derivative_type(instrument_type)`
- `theoretical_forward_price(spot, maturity_years, rate, income_yield)`
- `price_linear_derivative(instrument_type, spot, maturity_years, rate, income_yield, entry_price, quantity, multiplier, scenario_spot)`

Main formulas:

- `F = S * exp((r - q)T)`
- `discount_factor = exp(-rT)`
- `PnL_vs_entry = (F_current - F_entry) * quantity * multiplier`

## 9.4 `services/linear_risk.py`

Purpose:

- compute linear derivative VaR / ES and scenario PnL

Functions:

- `returns_from_prices(prices)`
- `rolling_horizon_pnl(single_day_pnl, horizon_days)`
- `linear_derivative_var(spot, quantity, multiplier, confidence, horizon_days, mu_daily, sigma_daily, historical_prices, scenario_move_pct, instrument_type)`

Capabilities:

- parametric VaR / ES
- historical VaR / ES
- scenario PnL

Main logic:

- `exposure_cash = spot * quantity * multiplier`
- `mu_horizon = mu_daily * horizon_days`
- `sigma_horizon = sigma_daily * sqrt(horizon_days)`
- `PnL_mu = exposure_cash * mu_horizon`
- `PnL_sigma = |exposure_cash| * sigma_horizon`

## 9.5 `services/backtesting.py`

Purpose:

- validate VaR / ES models on rolling history

Functions:

- `_safe_log_probability(probability)`
- `_chi2_sf_df1(statistic)`
- `_chi2_sf_df2(statistic)`
- `rolling_historical_var_es(pnl, confidence, window)`
- `kupiec_pof_test(exceptions, alpha)`
- `christoffersen_independence_test(exceptions)`
- `christoffersen_conditional_coverage_test(exceptions, alpha)`
- `es_realized_shortfall_diagnostics(realized_pnl, var_pnl_thresholds, es_losses)`

Outputs:

- rolling realized PnL
- rolling VaR thresholds
- exception sequence
- `green / yellow / red` verdicts
- ES tail diagnostics

## 9.6 `services/risk_attribution.py`

Purpose:

- decompose Delta-Normal portfolio VaR by factor

Functions:

- `_portfolio_sigma(exposures, covariance_matrix)`
- `delta_normal_var_contributions(factor_names, delta_cash_values, mu_horizon_values, covariance_horizon, z_value)`

Outputs:

- portfolio mean
- portfolio sigma
- portfolio VaR
- marginal VaR by factor
- component VaR by factor
- component share by factor

## 9.7 `services/stress_testing.py`

Purpose:

- full-revaluation stress testing for option portfolios

Functions:

- `evaluate_full_revaluation_stress_scenario(positions, horizon_days, underlying_return_shocks, volatility_shift, rate_shift)`
- `build_standard_stress_scenarios(underlying_ids)`

Built-in scenario families:

- market down 10%
- market down 20%
- crash with higher volatility
- rates up
- rates down

Outputs:

- base portfolio value
- stressed portfolio value
- total PnL
- per-position stressed PnL

## 10. Data Adapter Modules

## 10.1 `services/tinkoff_service.py`

Functions:

- `similarity_score(str1, str2, threshold)`
- `find_instruments(name, token)`
- `_price_to_float(price)`
- `get_candles(figi, start_date, end_date, token)`

Purpose:

- legacy instrument search and price history

## 10.2 `services/moex_service.py`

Functions:

- `_rows_to_dicts(payload, table_name)`
- `_get_iss_json(session, url, params)`
- `_resolve_security_board(session, secid)`
- `get_market_instruments(session, engine, market)`
- `get_option_board(session, underlying_asset_code)`
- `get_instrument_candles(session, secid, start_date, end_date, engine, market)`

Purpose:

- live MOEX integration for the derivative flow
- automatic board resolution for candle downloads
- option-board loading
- market list browsing

## 11. User Workflows

## 11.1 One Asset

Use when:

- you want a simple risk estimate for one instrument

Flow:

1. Choose `API`, `Manual`, or `Random`
2. Select a risk preset
3. Run the calculation
4. Read VaR, ES, LVaR, and the plain-language risk status

## 11.2 Portfolio

Use when:

- you want covariance-based portfolio analytics

Flow:

1. Add instruments
2. Set weights
3. Select a date range
4. Run portfolio risk
5. Review VaR, efficient frontier, cumulative return, and correlation matrix

## 11.3 MOEX

Novice flow:

1. Select a market category
2. Load instruments
3. Choose one row
4. Load candles
5. Use auto-filled spot, `mu`, and `sigma`

Pro flow:

1. Choose engine and market directly
2. Load instrument list
3. Optionally load option board
4. Send selected rows into derivative tabs
5. Load candles by `SECID`

## 11.4 Options

Use when:

- you need price and Greeks for one option contract

Flow:

1. Fill the contract manually or from MOEX
2. Run pricing
3. Review price, Greeks, and position-level values
4. Copy the same contract into `Option Risk`

## 11.5 Futures & SPFI

Use when:

- you need pricing and linear risk for a futures / forward / SPFI position

Flow:

1. Fill spot, maturity, rate, carry, quantity, multiplier
2. Run pricing
3. Run linear risk
4. Review parametric, historical, and scenario outputs

## 11.6 Option Risk

Use when:

- you need analytical VaR and simulation for one option position

Flow:

1. Fill the option contract
2. Enter market assumptions (`mu`, `sigma`, horizon)
3. Choose random or fixed-seed Monte Carlo
4. Run the calculation
5. Compare:
   - Delta-Normal
   - Delta-Gamma
   - Delta-Gamma Monte Carlo
   - Full Revaluation Monte Carlo

## 11.7 Model Check

Use when:

- you need rolling validation of a VaR model

Flow:

1. Provide PnL history
2. Select confidence and window
3. Run backtest
4. Review exception counts, verdicts, and ES diagnostics

## 11.8 Factor Breakdown

Use when:

- you need to understand which factors consume portfolio VaR

Flow:

1. Enter factors, deltas, means, and covariance matrix
2. Run factor breakdown
3. Review marginal and component contributions

## 11.9 Stress Scenarios

Novice flow:

1. Choose a predefined scenario
2. Enter one option position
3. Run quick stress-check
4. Review built-in and custom scenario outputs

Pro flow:

1. Add one or more option positions through the structured position builder
2. Choose a scenario template or edit shocks manually
3. Run full stress test
4. Review scenario table and raw details

## 12. Local Run Instructions

## 12.1 Docker

Recommended command:

```bash
docker compose up --build
```

Open:

```text
http://127.0.0.1:8000
```

## 12.2 Local Python

If dependencies are installed:

```bash
python main.py
```

## 12.3 Environment

Optional:

- `TINKOFF_TOKEN`

Without `TINKOFF_TOKEN`:

- Tinkoff-based search and candles are limited
- manual mode, random mode, MOEX, and local derivative analytics still work

## 13. Deploy Notes

- Docker installs the T-Bank SDK from the official package registry
- clean Docker build is expected to succeed from scratch
- the running container exposes port `8000`

## 14. Current Limits

- the option engine is European-style only
- Delta-Gamma analytics are still approximations
- multifactor helpers exist in the service layer, but the current UI focuses on the single-factor path
- some MOEX underlyings may legitimately return empty option boards

## 15. Summary

The current architecture is:

- adapters load market data
- FastAPI endpoints validate requests and assemble responses
- service modules perform the mathematical work
- the frontend presents a simplified user flow for non-experts and a fuller workspace for advanced users

This means the platform now supports both:

- old risk-calculator workflows
- new derivative and model-validation workflows

inside one local Docker-ready application.
