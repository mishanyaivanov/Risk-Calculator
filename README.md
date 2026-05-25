# Risk Analytics Platform

## 1. Project Purpose

This project is a local web-based risk analytics platform built around a FastAPI backend, a single-page Jinja frontend, and a Python mathematical engine.

The platform started as a portfolio risk calculator and was later expanded into a broader decision-support tool with:

- market-data adapters
- derivative pricing
- nonlinear risk analytics
- stress testing
- backtesting
- factor attribution
- bond / swap analysis
- explainability and guided next-step logic
- PDF reporting

The final product is intended to behave not only like a calculator, but like a structured analytics workspace.

---

## 2. Final Scope

The current release covers:

- single-asset market risk
- portfolio market risk
- option pricing and Greeks
- option VaR with Monte Carlo and full revaluation
- futures / forward / SPFI pricing
- linear derivative risk
- model backtesting
- factor risk attribution
- deterministic stress testing
- bond cashflow and swap-overlay analysis
- explainability, copilot, hedge scenarios, and PDF reporting

The final release intentionally avoids adding more heavy mathematics. The emphasis is on correctness, usability, reporting quality, consistent UX, and professional presentation.

---

## 3. Runtime Architecture

The application is organized into five layers.

### 3.1 Frontend Layer

Primary file:

- `templates/index.html`

Responsibilities:

- render the whole workspace in one page
- switch between `Basic` and `Pro` modes
- collect inputs
- show forms, cards, charts, status strips, and inline errors
- coordinate cross-tab data transfer
- create report requests after calculations are completed

### 3.2 API Layer

Primary file:

- `main.py`

Responsibilities:

- define request models
- validate input
- orchestrate service calls
- normalize responses for the frontend
- expose search, analytics, stress, and reporting endpoints

### 3.3 Data Adapter Layer

Files:

- `services/tinkoff_service.py`
- `services/moex_service.py`

Responsibilities:

- fetch or cache market instruments
- load candles and metadata
- expose provider-specific market data in a project-friendly format

These modules are adapters only. They do not perform the risk calculations themselves.

### 3.4 Mathematical Engine Layer

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
- `services/bond_swap.py`

Responsibilities:

- transform prices into PnL
- compute VaR / ES / LVaR
- compute covariance-based portfolio risk
- price derivatives
- simulate nonlinear option PnL
- validate model behavior on history
- decompose factor risk
- reprice portfolios under stress
- build bond cash flows and floating-leg overlays

### 3.5 Service Intelligence Layer

Files:

- `services/excel_import.py`
- `services/explainability.py`
- `services/risk_copilot.py`
- `services/hedge_constructor.py`
- `services/reporting.py`

Responsibilities:

- reduce input friction through Excel / CSV import
- translate raw metrics into plain-language summaries
- highlight the most important signals
- suggest next analytical actions
- build quick hedge scenarios
- generate downloadable PDF reports

---

## 4. UI Modes

The product supports two user modes.

### 4.1 Basic Mode

Basic mode is the shortest path through the product.

Visible tabs:

- `One Asset`
- `Portfolio`
- `MOEX`
- `Stress Scenarios`

Basic-mode support features:

- Excel / CSV import
- plain-language result summaries
- `Risk Copilot`
- `Hedge Constructor`
- minimal clutter

Design goals:

- keep only the fastest workflows visible
- avoid raw JSON in the main path
- expose only the most useful fields
- use clear wording and direct next-step messages

### 4.2 Pro Mode

Pro mode exposes the full analytical workspace.

Visible tabs:

- all Basic tabs
- `Options`
- `Futures & SPFI`
- `Option Risk`
- `Model Check`
- `Factor Breakdown`
- `Bond & Swap`

Design goals:

- full analytical coverage
- advanced controls
- structured builders instead of raw JSON where practical
- more detailed diagnostics without changing the core workflow model

---

## 5. Functional Map

### 5.1 Core User Flows

- `One Asset`
- `Portfolio`
- `MOEX`
- `Stress Scenarios`

### 5.2 Advanced Analytical Flows

- `Options`
- `Futures & SPFI`
- `Option Risk`
- `Model Check`
- `Factor Breakdown`
- `Bond & Swap`

### 5.3 Product Extensions

- Excel / CSV import
- explainability
- `Risk Copilot`
- `Hedge Constructor`
- PDF reporting
- shared Tinkoff file-cache
- bridges between workflows

---

## 6. Market Data Adapters

### 6.1 Tinkoff

Used for:

- instrument search
- one-asset historical candles
- portfolio candle history

Important implementation note:

Tinkoff search no longer depends on a live API round-trip for every request.

The standard search flow now uses a shared file-cache:

- cache file: `cache/tinkoff_instruments_cache.json`
- shared for the entire service
- not user-specific
- refreshed when stale
- deduplicated by `FIGI`

Normal flow:

1. user enters a ticker or part of a name
2. `/api/search` searches the cache file
3. exact ticker matches are ranked first
4. similar results are still returned below the exact match

Fallback flow:

1. user clicks the small `API` button
2. `/api/search_live` performs a live Tinkoff search
3. found results can be merged back into the shared cache

Refresh flow:

- `/api/tinkoff_cache/rebuild` rebuilds the entire file
- the service can refresh automatically when the cache becomes stale

### 6.2 MOEX

Used for:

- market instrument browsing
- option board loading
- candle loading by `SECID`
- deriving spot, daily `mu`, and daily `sigma`
- feeding derivative tabs with market context

MOEX is not used as the pricing engine. Pricing and risk are still computed locally in Python.

---

## 7. API Endpoints

### 7.1 Core UI and Search

- `GET /`
  - serves the main UI
- `GET /api/search`
  - shared-cache Tinkoff search
- `GET /api/search_live`
  - live Tinkoff fallback search
- `POST /api/tinkoff_cache/rebuild`
  - full cache rebuild

### 7.2 Single Asset and Portfolio

- `POST /api/calculate`
  - single-asset risk
- `POST /api/import_prices_file`
  - import one-asset price history from Excel / CSV
- `POST /api/calculate_portfolio`
  - portfolio risk
- `POST /api/import_portfolio_file`
  - import portfolio rows from Excel / CSV

### 7.3 MOEX and Derivatives

- `GET /api/moex/instruments`
  - instrument list
- `GET /api/moex/option_board/{underlying_asset_code}`
  - option board
- `POST /api/moex/candles`
  - candle history
- `POST /api/option_pricing`
  - Black-Scholes price and Greeks
- `POST /api/option_var`
  - option VaR / ES / Monte Carlo / full revaluation
- `POST /api/forward_pricing`
  - linear derivative pricing
- `POST /api/linear_var`
  - linear derivative risk

### 7.4 Validation and Decomposition

- `POST /api/backtest`
  - model validation
- `POST /api/risk_attribution`
  - factor contribution analysis
- `POST /api/stress_test`
  - deterministic stress scenarios
- `POST /api/bond_swap`
  - bond and swap-overlay package

### 7.5 Reporting

- `POST /api/report/single/create`
  - create a `One Asset` PDF report
- `POST /api/report/portfolio/create`
  - create a `Portfolio` PDF report
- `POST /api/report/option-risk/create`
  - create an `Option Risk` PDF report
- `GET /api/report/download/{report_id}`
  - download a generated report

---

## 8. Detailed Tab-by-Tab Functionality

## 8.1 One Asset

Purpose:

- estimate risk for one instrument or one manually provided price path

Input modes:

- `API`
- `Manual`
- `Random`

Capabilities:

- Tinkoff search
- manual price input
- random sample generation
- Excel / CSV import
- parametric VaR
- historical VaR
- expected shortfall
- liquidity-adjusted VaR
- plain-language explanation
- `Risk Copilot`
- `Hedge Constructor`
- PDF report generation

Main outputs:

- price history chart
- VaR
- ES
- LVaR
- interpretation summary
- copilot signals
- hedge scenarios

## 8.2 Portfolio

Purpose:

- evaluate multi-asset covariance risk

Input model:

- list of instruments
- editable weights
- date range
- confidence level

Important scale convention:

- the portfolio is normalized to a capital base of `1.0`
- portfolio VaR is therefore shown as a share of normalized capital
- annual return and annual volatility are shown as percentages
- cumulative growth is shown from `1.00`

Capabilities:

- Tinkoff-based portfolio search
- Excel / CSV import
- automatic weight normalization when the sum is positive
- covariance VaR
- annualized return
- annualized volatility
- correlation matrix
- efficient frontier
- cumulative return chart
- allocation chart
- plain-language explanation
- `Risk Copilot`
- `Hedge Constructor`
- PDF report generation

Main outputs:

- normalized portfolio VaR
- annual volatility
- annual return
- efficient frontier with the current portfolio highlighted
- normalized cumulative growth chart
- correlation heatmap
- allocation pie chart

## 8.3 MOEX

Purpose:

- load live market context for derivatives

Basic flow:

1. choose a market category
2. load instruments
3. select a row
4. load candles
5. auto-fill market context

Pro flow:

1. choose engine and market directly
2. load instrument list
3. optionally load option board
4. send rows into derivative screens
5. load candles by `SECID`

Capabilities:

- browse exchange instruments
- load option boards
- load candles
- derive spot, daily `mu`, and daily `sigma`
- feed derivative forms with live market context

## 8.4 Options

Purpose:

- price one option contract and compute Greeks

Capabilities:

- Black-Scholes pricing
- `d1`, `d2`
- delta
- gamma
- vega
- theta
- rho
- position scaling through quantity and multiplier
- bridge into `Option Risk`

Interpretation focus:

- moneyness
- intrinsic vs time value
- delta sensitivity
- vega / theta balance

## 8.5 Futures & SPFI

Purpose:

- price a linear derivative and estimate linear risk

Capabilities:

- fair price
- carry
- entry PnL
- scenario PnL
- parametric linear VaR
- historical linear VaR
- scenario loss
- direct loading from `Hedge Constructor`

## 8.6 Option Risk

Purpose:

- estimate risk for one option position with approximation and simulation methods

Capabilities:

- Delta-Normal approximation
- Delta-Gamma approximation
- Monte Carlo simulation
- fixed or random seed
- full revaluation
- PnL distribution histogram
- PDF report generation

Main outputs:

- Delta-Normal VaR
- Delta-Gamma VaR
- Monte Carlo VaR
- Monte Carlo ES
- optional Full Revaluation VaR / ES
- MC histogram
- interpretation panel

## 8.7 Model Check

Purpose:

- validate VaR behavior on historical PnL

Capabilities:

- rolling historical VaR / ES
- POF test
- independence test
- conditional coverage
- ES diagnostics
- qualitative verdict interpretation

## 8.8 Factor Breakdown

Purpose:

- explain what drives portfolio VaR in a factor model

Capabilities:

- delta-normal factor decomposition
- portfolio sigma
- marginal VaR
- component VaR
- concentration interpretation

## 8.9 Bond & Swap

Purpose:

- value bond cash flows
- calibrate a floating overlay
- compare coupon-only and full-issue hedge constructions

Capabilities:

- cashflow schedule generation
- coupon PV
- principal PV
- total PV
- fair spread in bps
- scenario sensitivity under 1Y-rate changes
- guided interpretation of practical vs unrealistic hedge variants

Result structure:

1. hedge options
2. scenario impact
3. cashflow schedule
4. warnings

## 8.10 Stress Scenarios

Purpose:

- test resilience under deterministic adverse scenarios

Basic flow:

1. choose a preset
2. define one option position
3. run stress
4. review interpretation and scenario table

Pro flow:

1. add one or more positions
2. define `underlying_id`
3. apply a preset or custom shocks
4. run full stress
5. review scenario table and ranking chart

Capabilities:

- preset scenarios
- custom underlying shocks
- volatility shift
- rate shift
- multi-position stress
- scenario ranking chart

---

## 9. Bridges and Cross-Workflow Transfers

One of the strongest UX additions in this project is the bridge system.

The user does not always need to retype the same contract or market state in multiple tabs.

### 9.1 Shared Asset Context

The selected asset context can feed:

- `Options`
- `Futures & SPFI`
- `Option Risk`
- `Model Check`
- `Stress Scenarios`

Transferred fields depend on the target, but can include:

- last price
- price history
- daily `mu`
- daily `sigma`
- position size
- multiplier
- PnL series

### 9.2 Options -> Option Risk

The `Send To Option Risk` action copies:

- option type
- spot
- strike
- maturity
- rate
- volatility
- dividend yield
- quantity
- multiplier

### 9.3 Hedge Constructor Bridges

Single-asset hedge scenarios can open:

- `Futures & SPFI`
- `Options`

Portfolio hedge scenarios can update:

- `Portfolio` weights directly

These bridges are action-oriented, not just informational.

---

## 10. Explainability, Copilot, and Hedge Logic

## 10.1 Explainability Layer

Files:

- `services/explainability.py`

Purpose:

- convert the raw result into a concise structured summary

Output structure:

- `severity`
- `label`
- `headline`
- `summary`
- `takeaways`
- `next_steps`

This layer does not invent new math. It interprets existing metrics.

## 10.2 Risk Copilot

Files:

- `services/risk_copilot.py`

Purpose:

- highlight what matters most in the result

Output structure:

- `title`
- `severity`
- `one_liner`
- `main_message`
- `signals`
- `actions`

The copilot is rule-based, not LLM-generated.

It uses:

- current risk share
- ES / VaR relationship
- liquidity add-on
- concentration
- correlation
- risk / return balance

## 10.3 Hedge Constructor

Files:

- `services/hedge_constructor.py`

Purpose:

- offer a curated set of practical scenarios
- compare before / after
- support immediate next-step workflows

The hedge suggestions are deterministic and scenario-based.

They are not an optimizer and do not claim to be globally optimal.

---

## 11. Exact Hedge Scenarios and Conditions

## 11.1 Single-Asset Hedge Scenarios

The single-asset hedge constructor currently builds four quick scenarios.

### Scenario 1: Trim the position by 25%

Fields:

- `id = trim_25`
- `type = size_reduction`
- `factor = 0.75`

Meaning:

- keep 75% of the position
- scale risk approximately linearly

Action text:

- reduce roughly one quarter of the current position

### Scenario 2: Trim the position by 50%

Fields:

- `id = trim_50`
- `type = size_reduction`
- `factor = 0.50`

Meaning:

- keep 50% of the position
- scale risk approximately linearly

Action text:

- cut the current exposure in half

### Scenario 3: Add a 50% linear hedge

Fields:

- `id = futures_50`
- `type = linear_hedge`
- `factor = 0.50`

Meaning:

- approximate a short futures / SPFI hedge on 50% of spot exposure
- residual risk is scaled to 50% of the original first-order risk

Quick action:

- open in `Futures & SPFI`

Generated hedge payload:

- `instrument_type = futures`
- `spot = last_price`
- `entry_price = last_price`
- `maturity_years = 0.25`
- `rate = 0.05`
- `income_yield = 0.0`
- `quantity = position_size * 0.50`
- `multiplier = 1.0`
- `scenario_spot = last_price * 0.95`
- `hedge_ratio = 0.50`

### Scenario 4: Add a 75% linear hedge

Fields:

- `id = futures_75`
- `type = linear_hedge`
- `factor = 0.25`

Meaning:

- approximate a short futures / SPFI hedge on 75% of spot exposure
- residual risk is scaled to 25% of the original first-order risk

Quick action:

- open in `Futures & SPFI`

Generated hedge payload:

- `hedge_ratio = 0.75`
- `quantity = position_size * 0.75`
- other fields follow the same pattern as the 50% hedge

### Protective Put Bridge

This is not one of the four core scenario cards, but it is always available as a bridge action.

Payload:

- `option_type = put`
- `spot = last_price`
- `strike = 90% of spot`
- `maturity_years = 0.25`
- `rate = 0.05`
- `volatility = 0.25`
- `dividend_yield = 0.0`
- `quantity = position_size`
- `multiplier = 1.0`

Purpose:

- move the user from a directional position into a nonlinear downside-protection workflow

## 11.2 Portfolio Hedge Scenarios

The portfolio hedge constructor currently builds three quick scenarios.

### Scenario 1: Move closer to equal weights

Fields:

- `id = equal_weight`
- weights become `1 / number_of_assets` for each asset

Meaning:

- create a diversification baseline

Quick action:

- apply these weights directly into the portfolio table

### Scenario 2: Cut the largest position by 15 percentage points

Fields:

- `id = trim_largest_15pp`
- remove `0.15` from the largest weight
- redistribute the removed weight across the remaining assets

Meaning:

- show a more realistic partial rebalance

Quick action:

- apply these weights directly into the portfolio table

### Scenario 3: Add a 20% protective overlay

Fields:

- `id = market_overlay_20`
- `scale_factor = 0.80`

Meaning:

- approximate a short overlay that reduces net market exposure to 80%
- the model keeps annual return unchanged in this quick scenario
- VaR and annual volatility are scaled down by the overlay factor

This is a decision-support approximation, not a full overlay pricing engine.

## 11.3 Severity Logic for Hedge Cards

The hedge constructor uses the same risk-share severity buckets:

- `green` if loss share `< 2%`
- `yellow` if loss share `< 5%`
- `red` otherwise

This applies to the `after` state of the scenario.

---

## 12. Reporting System

Files:

- `services/reporting.py`
- report endpoints in `main.py`

The reporting system is backend-generated and report-oriented.

### 12.1 Report Flow

1. user runs a calculation
2. frontend stores the last valid result
3. user clicks `Create PDF Report`
4. frontend sends:
   - calculation payload
   - result payload
   - chart images
5. backend generates PDF bytes
6. report is stored temporarily in memory
7. user clicks `Download PDF`

### 12.2 Report Types

- `One Asset`
- `Portfolio`
- `Option Risk`

### 12.3 Report Storage

The report store is in-memory.

Properties:

- temporary
- max report count limit
- TTL-based cleanup

This is good for local or demo usage, but not intended as permanent archival storage.

### 12.4 Report Content by Type

#### One Asset Report

Includes:

- input snapshot
- current position value
- parametric VaR
- historical VaR
- ES
- stressed LVaR
- interpretation summary
- executive bullets
- price history chart
- methodology note

#### Portfolio Report

Includes:

- input snapshot
- normalization base
- portfolio VaR on base `1.0`
- annual return / volatility
- portfolio composition
- interpretation summary
- executive bullets
- efficient frontier
- cumulative return chart
- correlation matrix
- allocation chart
- methodology note

#### Option Risk Report

Includes:

- input snapshot
- simulations, horizon, seed mode
- Delta-Normal VaR
- Delta-Gamma VaR
- Monte Carlo VaR / ES
- Full Revaluation VaR / ES
- interpretation summary
- Monte Carlo histogram
- methodology note

---

## 13. Recommendation Logic: Fixed or Dynamic?

The platform does not use a language model to invent recommendations.

The recommendation logic is rule-based and deterministic.

### 13.1 What the Recommendation Layers Depend On

For single asset:

- parametric VaR
- historical VaR
- ES
- stressed LVaR
- loss share vs position size

For portfolio:

- portfolio VaR
- annual return
- annual volatility
- largest weight
- average absolute correlation

### 13.2 What Is Fixed

- the set of scenario templates
- the threshold logic
- the wording families

### 13.3 What Is Dynamic

- severity
- highlighted message
- signal values
- which actions appear
- which hedge card looks best after scaling

In short:

- not hardcoded one-text-for-all
- not LLM-generated
- rule-based on top of calculated metrics

---

## 14. Search Cache Behavior

The Tinkoff cache is intentionally simple and file-based.

### 14.1 Why It Exists

- live Tinkoff search can feel slow
- common tickers should be available quickly
- the service needs one shared instrument dictionary for all users

### 14.2 What the Cache Stores

Each record can include:

- `ticker`
- `figi`
- `name`
- `type`

### 14.3 Ranking Logic

Search prioritizes:

1. exact ticker match
2. ticker prefix
3. exact name
4. ticker substring
5. name substring
6. fuzzy similarity

Then the result is sorted with a type preference:

- shares
- bonds
- ETFs
- currencies

### 14.4 Anti-Garbage Logic

The cache is not intended to become an infinite dump.

Safeguards:

- deduplication by `FIGI`
- full rebuild endpoint
- stale-cache refresh logic
- shared one-file structure instead of user-specific fragments

---

## 15. Normalization and Scale Conventions

This is an important project-wide consistency rule.

### 15.1 Single Asset

- position-level cash metrics are shown in money terms
- risk share is shown relative to current position size

### 15.2 Portfolio

- portfolio analytics are normalized to a capital base of `1.0`
- VaR is therefore interpreted as a share of capital
- annual return and annual volatility are percentages
- cumulative chart starts from `1.00`

This convention was chosen to remove ambiguity between “growth from 1” and “growth from 100000”.

### 15.3 Option Risk

- approximation and simulation outputs are shown in PnL units derived from the cash Greeks and the selected contract scale

---

## 16. Final Manual QA Checklist

Recommended final QA order:

1. `One Asset`
2. `Portfolio`
3. `MOEX`
4. `Options`
5. `Option Risk`
6. `Futures & SPFI`
7. `Stress Scenarios`
8. `Model Check`
9. `Factor Breakdown`
10. `Bond & Swap`
11. PDF generation
12. Tinkoff cache search
13. bridges between tabs

### 16.1 Key things to confirm

- no broken buttons
- no `undefined`
- no `NaN`
- no Russian UI text
- no stale selected asset after reload
- correct percent vs cash formatting
- charts render cleanly
- report generation works
- cache search returns both exact and similar results

---

## 17. Local Run Instructions

### 17.1 Docker

Recommended:

```bash
docker compose up --build
```

Open:

```text
http://127.0.0.1:8000
```

### 17.2 Local Python

If dependencies are already installed:

```bash
python main.py
```

### 17.3 Environment

Optional:

- `TINKOFF_TOKEN`
- `TINKOFF_CACHE_REFRESH_HOUR_UTC`
- `TINKOFF_CACHE_MAX_AGE_HOURS`

Without `TINKOFF_TOKEN`:

- Tinkoff live search is unavailable
- manual, random, MOEX, and local analytical flows still work

---

## 18. Current Boundaries

The final release is strong, but not pretending to be a full institutional platform.

Important limits:

- option pricing is European-style
- Delta-Gamma methods remain approximations
- hedge constructor is scenario-based, not optimization-based
- PDF reports are temporary-download artifacts, not permanent archives
- the shared Tinkoff cache is file-based, not distributed

These are acceptable boundaries for a local analytical service and course-level product.

---

## 19. Final Product Positioning

The final product should be described as:

**a risk analytics workspace with decision-support features**

not merely:

**a collection of formulas**

The product now:

- calculates
- explains
- compares
- suggests
- transfers context between analytical blocks
- documents the result through PDF reporting

That combination is the main value of the final version.
