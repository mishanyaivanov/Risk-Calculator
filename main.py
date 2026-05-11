from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, Response
from fastapi import UploadFile, File
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Any, List, Optional, Dict
import uvicorn
import os
import random
import aiohttp
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from services.tinkoff_service import find_instruments, get_candles
from services.risk_calculator import (
    pnl_from_prices, 
    historical_var_discrete, 
    expected_shortfall_discrete, 
    parametric_var,
    parse_price_input,
    generate_random_prices,
    normal_liquidation_cost,
    stressed_liquidation_cost,
    linear_unwind_adjusted_var
)
from services.portfolio_manager import calculate_portfolio_var, generate_efficient_frontier
from services.backtesting import (
    rolling_historical_var_es,
    christoffersen_conditional_coverage_test,
    es_realized_shortfall_diagnostics,
)
from services.risk_attribution import delta_normal_var_contributions
from services.stress_testing import evaluate_full_revaluation_stress_scenario, build_standard_stress_scenarios
from services.moex_service import get_market_instruments, get_option_board, get_instrument_candles
from services.option_pricing import black_scholes_price_and_greeks
from services.option_var import (
    option_var_moment_approximations,
    simulate_delta_gamma_pnl,
    simulate_full_revaluation_pnl,
)
from services.forward_pricing import price_linear_derivative
from services.linear_risk import linear_derivative_var
from services.bond_swap import evaluate_bond_swap_package
from services.excel_import import parse_price_series_file, parse_portfolio_file
from services.explainability import build_single_asset_explanation, build_portfolio_explanation
from services.risk_copilot import build_single_asset_copilot, build_portfolio_copilot
from services.hedge_constructor import (
    build_single_asset_hedge_constructor,
    build_portfolio_hedge_constructor,
)
from services.reporting import build_single_asset_report, build_portfolio_report, ReportStore

app = FastAPI()
templates = Jinja2Templates(directory="templates")
report_store = ReportStore()


def has_real_tinkoff_token(token: Optional[str]) -> bool:
    return bool(token and token.strip() and token.strip() != "Token")


def build_risk_status(var_loss: float, position_value: float) -> Dict[str, float | str]:
    base_value = abs(position_value)
    share_pct = (var_loss / base_value * 100.0) if base_value > 1e-12 else 0.0

    if share_pct < 2.0:
        severity = "green"
        label = "Низкий риск"
        guidance = "Потеря в плохой день невелика относительно размера позиции."
    elif share_pct < 5.0:
        severity = "yellow"
        label = "Средний риск"
        guidance = "Позиция чувствительна к плохому дню. Стоит следить за размером позиции и ликвидностью."
    else:
        severity = "red"
        label = "Высокий риск"
        guidance = "Потенциальная потеря заметна относительно размера позиции. Проверьте размер сделки и стресс-сценарии."

    return {
        "severity": severity,
        "label": label,
        "loss_share_pct": share_pct,
        "summary": guidance,
    }


def resolve_tinkoff_figi(figi: Optional[str], instrument_query: Optional[str], token: str) -> str:
    if figi:
        return figi

    query = (instrument_query or "").strip()
    if not query:
        raise ValueError("Enter a ticker or choose an instrument from search results.")

    results = find_instruments(query, token)
    if not results:
        raise ValueError("Instrument was not found in Tinkoff search. Try another ticker or use Manual mode.")

    query_upper = query.upper()
    exact_ticker_matches = [
        item for item in results
        if str(item.get("ticker", "")).upper() == query_upper and item.get("figi")
    ]
    if len(exact_ticker_matches) == 1:
        return str(exact_ticker_matches[0]["figi"])

    exact_name_matches = [
        item for item in results
        if str(item.get("name", "")).strip().upper() == query_upper and item.get("figi")
    ]
    if len(exact_name_matches) == 1:
        return str(exact_name_matches[0]["figi"])

    valid_results = [item for item in results if item.get("figi")]
    if len(valid_results) == 1:
        return str(valid_results[0]["figi"])

    raise ValueError("Several instruments match the query. Please click one item in the search results list.")


def try_resolve_portfolio_figi(ticker: str, token: Optional[str]) -> Optional[str]:
    if not ticker or not has_real_tinkoff_token(token):
        return None

    try:
        results = find_instruments(ticker, token)
    except Exception:
        return None

    ticker_upper = ticker.strip().upper()
    for item in results:
        if str(item.get("ticker", "")).upper() == ticker_upper and item.get("figi"):
            return str(item["figi"])

    for item in results:
        if item.get("figi"):
            return str(item["figi"])
    return None

class CalculationRequest(BaseModel):
    mode: str
    figi: Optional[str] = None
    instrument_query: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    manual_prices: Optional[str] = None
    confidence: float = 0.95
    position_size: float = 1.0
    spread_percent: Optional[float] = 0.1
    liquidation_days: Optional[int] = 1
    sigma_spread_percent: Optional[float] = 0.05

class PortfolioItem(BaseModel):
    figi: str
    ticker: str
    weight: float

class PortfolioRequest(BaseModel):
    items: List[PortfolioItem]
    start_date: str
    end_date: str
    confidence: float = 0.95
    portfolio_value: float = 100000.0


class ReportRequest(BaseModel):
    calculation: Dict[str, Any]
    result: Dict[str, Any]
    chart_images: Optional[Dict[str, str]] = None

class BacktestRequest(BaseModel):
    pnl: List[float]
    confidence: float = 0.95
    window: int = 250

class RiskAttributionRequest(BaseModel):
    factor_names: List[str]
    delta_cash_values: List[float]
    mu_horizon_values: List[float]
    covariance_horizon: List[List[float]]
    z_value: float

class StressTestPosition(BaseModel):
    spot: float
    strike: float
    quantity: float
    underlying_id: str = "U1"
    option_type: str = "call"
    multiplier: float = 1.0
    maturity_years: float
    rate: float
    volatility: float
    dividend_yield: float

class StressTestRequest(BaseModel):
    positions: List[StressTestPosition]
    horizon_days: int
    underlying_return_shocks: Dict[str, float]
    volatility_shift: float = 0.0
    rate_shift: float = 0.0

class MoexCandlesRequest(BaseModel):
    secid: str
    start_date: str
    end_date: str
    engine: Optional[str] = None
    market: Optional[str] = None

class OptionPricingRequest(BaseModel):
    option_type: str
    spot: float
    strike: float
    maturity_years: float
    rate: float
    volatility: float
    dividend_yield: float
    quantity: float = 1.0
    multiplier: float = 1.0

class OptionPositionRequest(BaseModel):
    option_type: str
    spot: float
    strike: float
    maturity_years: float
    rate: float
    volatility: float
    dividend_yield: float = 0.0
    quantity: float = 1.0
    multiplier: float = 1.0
    underlying_id: str = "U1"

class OptionVaRRequest(BaseModel):
    delta_cash: float
    gamma_cash: float
    theta_horizon: float
    mu_horizon: float
    sigma_horizon: float
    z_value: float
    simulations: int = 50000
    seed: Optional[int] = None
    confidence: float = 0.95
    full_revaluation: bool = False
    horizon_days: int = 1
    full_revaluation_position: Optional[OptionPositionRequest] = None
    vol_mean_horizon: float = 0.0
    vol_sigma_horizon: float = 0.0
    rate_mean_horizon: float = 0.0
    rate_sigma_horizon: float = 0.0

class ForwardPricingRequest(BaseModel):
    instrument_type: str = "futures"
    spot: float
    maturity_years: float
    rate: float
    income_yield: float = 0.0
    entry_price: Optional[float] = None
    quantity: float = 1.0
    multiplier: float = 1.0
    scenario_spot: Optional[float] = None

class LinearVaRRequest(BaseModel):
    instrument_type: str = "linear_derivative"
    spot: float
    quantity: float = 1.0
    multiplier: float = 1.0
    confidence: float = 0.95
    horizon_days: int = 1
    mu_daily: Optional[float] = None
    sigma_daily: Optional[float] = None
    historical_prices: Optional[List[float]] = None
    scenario_move_pct: Optional[float] = None


class BondSwapRequest(BaseModel):
    issue: Dict[str, Any]
    curve: List[Dict[str, Any]]
    valuation_date: Optional[str] = None
    rate_scenarios_1y: Optional[List[Any]] = None
    hedge_ratios: List[float] = [1.0, 0.75, 0.5]
    include_full_issue_variant: bool = True

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse(request, "index.html")

@app.get("/api/search")
async def search_instrument(query: str):
    token = os.getenv("TINKOFF_TOKEN")
    if not has_real_tinkoff_token(token):
        raise HTTPException(
            status_code=400,
            detail="TINKOFF_TOKEN is not set. Add a real token or use Manual / Random mode."
        )
        
    results = find_instruments(query, token)
    return results


@app.post("/api/import_prices_file")
async def import_prices_file(file: UploadFile = File(...)):
    content = b""
    try:
        content = await file.read()
        if not content:
            raise ValueError("The uploaded file is empty.")
        return parse_price_series_file(content, file.filename or "uploaded_file")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        content = b""
        await file.close()


@app.post("/api/import_portfolio_file")
async def import_portfolio_file(file: UploadFile = File(...)):
    content = b""
    try:
        content = await file.read()
        if not content:
            raise ValueError("The uploaded file is empty.")

        parsed = parse_portfolio_file(content, file.filename or "uploaded_file")
        token = os.getenv("TINKOFF_TOKEN")
        rows = []
        resolved_count = 0
        unresolved_count = 0

        for row in parsed["rows"]:
            ticker = str(row.get("ticker", "") or "").strip()
            figi = str(row.get("figi", "") or "").strip()
            if not figi:
                figi = try_resolve_portfolio_figi(ticker, token) or ""
            if figi:
                resolved_count += 1
            else:
                unresolved_count += 1

            rows.append(
                {
                    "ticker": ticker,
                    "figi": figi,
                    "weight": float(row["weight"]),
                }
            )

        return {
            **parsed,
            "rows": rows,
            "resolved_figi_count": resolved_count,
            "missing_figi_count": unresolved_count,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        content = b""
        await file.close()

@app.post("/api/calculate")
async def calculate_risk(request: CalculationRequest):
    prices = []
    candles_data = [] 
    
    try:
        if request.mode == 'tinkoff':
            token = os.getenv("TINKOFF_TOKEN")
            if not has_real_tinkoff_token(token):
                raise ValueError("TINKOFF_TOKEN is not set. Please use Manual or Random mode.")
            
            resolved_figi = resolve_tinkoff_figi(request.figi, request.instrument_query, token)
                
            candles = get_candles(resolved_figi, request.start_date, request.end_date, token)
            if not candles or len(candles) < 2:
                raise ValueError("Not enough data from Tinkoff API (need at least 2 days).")
            
            prices = [c['close'] for c in candles]
            candles_data = candles

        elif request.mode == 'manual':
            if not request.manual_prices:
                raise ValueError("Please enter prices for Manual mode.")
            prices = parse_price_input(request.manual_prices)
            start_dt = datetime.now() - timedelta(days=len(prices))
            for i, p in enumerate(prices):
                dt = start_dt + timedelta(days=i)
                candles_data.append({
                    'date': dt.strftime('%Y-%m-%d'),
                    'open': p, 'high': p, 'low': p, 'close': p
                })

        elif request.mode == 'random':
            prices = generate_random_prices(days=100)
            start_dt = datetime.now() - timedelta(days=100)
            for i, p in enumerate(prices):
                dt = start_dt + timedelta(days=i)
                high = p * (1 + random.uniform(0, 0.01))
                low = p * (1 - random.uniform(0, 0.01))
                open_p = (high + low) / 2 
                candles_data.append({
                    'date': dt.strftime('%Y-%m-%d'),
                    'open': open_p, 'high': high, 'low': low, 'close': p
                })
        
        else:
            raise ValueError("Invalid mode selected.")

        if len(prices) < 2:
             raise ValueError("Not enough price data (need at least 2 prices).")

        pnl = pnl_from_prices(prices, position_size=request.position_size)

        h_var = historical_var_discrete(pnl, request.confidence)
        es = expected_shortfall_discrete(pnl, request.confidence)
        p_var = parametric_var(pnl, request.confidence)

        last_price = prices[-1]
        position_value = last_price * request.position_size
        
        lvar_metrics = {}
        if request.spread_percent is not None:
            lc_normal = normal_liquidation_cost(position_value, request.spread_percent)
            lc_stressed = stressed_liquidation_cost(
                position_value, 
                request.spread_percent, 
                request.confidence, 
                request.sigma_spread_percent or 0.05
            )
            
            base_var_val = p_var.get("var_loss", 0)
            lvar_normal = base_var_val + lc_normal
            lvar_stressed = base_var_val + lc_stressed
            
            lvar_unwind = 0
            if request.liquidation_days and request.liquidation_days > 1:
                lvar_unwind = linear_unwind_adjusted_var(base_var_val, request.liquidation_days)
            else:
                lvar_unwind = base_var_val

            lvar_metrics = {
                "lc_normal": lc_normal,
                "lc_stressed": lc_stressed,
                "lvar_normal": lvar_normal,
                "lvar_stressed": lvar_stressed,
                "lvar_unwind": lvar_unwind,
                "liquidation_days": request.liquidation_days
            }

        risk_status = build_risk_status(
            var_loss=float(p_var.get("var_loss", 0.0)),
            position_value=position_value,
        )
        explanation = build_single_asset_explanation(
            risk_status=risk_status,
            historical_var_loss=float(h_var.get("var_loss", 0.0)),
            expected_shortfall_loss=float(es.get("es_loss", 0.0)),
            lvar_loss=float(lvar_metrics.get("lvar_stressed")) if lvar_metrics.get("lvar_stressed") is not None else None,
        )
        copilot = build_single_asset_copilot(
            risk_status=risk_status,
            historical_var=h_var,
            expected_shortfall=es,
            parametric_var=p_var,
            lvar=lvar_metrics,
            confidence=request.confidence,
        )
        hedge_constructor = build_single_asset_hedge_constructor(
            position_value=position_value,
            position_size=request.position_size,
            last_price=last_price,
            parametric_var_loss=float(p_var.get("var_loss", 0.0)),
            historical_var_loss=float(h_var.get("var_loss", 0.0)),
            expected_shortfall_loss=float(es.get("es_loss", 0.0)),
            stressed_lvar_loss=float(lvar_metrics.get("lvar_stressed")) if lvar_metrics.get("lvar_stressed") is not None else None,
        )

        return {
            "prices": prices,
            "candles": candles_data,
            "prices_count": len(prices),
            "last_price": prices[-1],
            "position_value": position_value,
            "historical_var": h_var,
            "es": es,
            "parametric_var": p_var,
            "lvar": lvar_metrics,
            "risk_status": risk_status,
            "explanation": explanation,
            "copilot": copilot,
            "hedge_constructor": hedge_constructor,
            "pnl_series": pnl
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/calculate_portfolio")
async def calculate_portfolio(request: PortfolioRequest):
    total_input_weight = sum(item.weight for item in request.items)
    if total_input_weight <= 0:
        raise HTTPException(status_code=400, detail="Portfolio weights must sum to a positive value.")

    token = os.getenv("TINKOFF_TOKEN")
    if not has_real_tinkoff_token(token):
        raise HTTPException(status_code=400, detail="TINKOFF_TOKEN is required for portfolio calculation.")

    try:
        data_frames = []
        weights_list = []
        
        for item in request.items:
            figi_to_use = item.figi or try_resolve_portfolio_figi(item.ticker, token)
            if not figi_to_use:
                continue

            candles = get_candles(figi_to_use, request.start_date, request.end_date, token)
            if not candles or len(candles) < 2:
                continue 
            
            df = pd.DataFrame(candles)
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
            
            col_name = item.ticker if item.ticker else item.figi
            df[col_name] = df['close'].pct_change()
            data_frames.append(df[[col_name]])
            weights_list.append(item.weight)

        if not data_frames:
            raise HTTPException(status_code=400, detail="No valid data found for any instrument.")

        full_df = pd.concat(data_frames, axis=1, join='inner')
        full_df.dropna(inplace=True)
        
        if full_df.empty:
             raise HTTPException(status_code=400, detail="No overlapping dates found for instruments.")

        returns_matrix = full_df.values
        weights_array = np.array(weights_list)
        total_weight = weights_array.sum()
        if total_weight <= 0:
            raise HTTPException(status_code=400, detail="Portfolio weights must sum to a positive value.")
        
        if abs(total_weight - 1.0) > 0.01:
             weights_array = weights_array / total_weight

        portfolio_metrics = calculate_portfolio_var(
            returns_matrix, 
            weights_array, 
            request.confidence, 
            request.portfolio_value
        )
        
        frontier_data = generate_efficient_frontier(returns_matrix, num_portfolios=500)
        
        portfolio_daily_returns = np.dot(returns_matrix, weights_array)
        portfolio_cum_return = np.cumprod(1 + portfolio_daily_returns)
        
        assets_cum_returns = (1 + full_df).cumprod()
        asset_names = full_df.columns.tolist()
        portfolio_status = build_portfolio_explanation(
            portfolio_metrics=portfolio_metrics,
            weights=weights_array.tolist(),
            asset_names=asset_names,
            correlation_matrix=full_df.corr().to_dict(),
            portfolio_value=request.portfolio_value,
        )
        portfolio_copilot = build_portfolio_copilot(
            portfolio_metrics=portfolio_metrics,
            weights=weights_array.tolist(),
            asset_names=asset_names,
            correlation_matrix=full_df.corr().to_dict(),
            portfolio_value=request.portfolio_value,
        )
        portfolio_hedge_constructor = build_portfolio_hedge_constructor(
            returns_matrix=returns_matrix,
            weights=weights_array.tolist(),
            asset_names=asset_names,
            confidence=request.confidence,
            portfolio_value=request.portfolio_value,
        )
        
        return {
            "portfolio_metrics": portfolio_metrics,
            "correlation_matrix": full_df.corr().to_dict(),
            "dates": full_df.index.strftime('%Y-%m-%d').tolist(),
            "assets_cumulative_returns": assets_cum_returns.to_dict(),
            "portfolio_cumulative_return": portfolio_cum_return.tolist(),
            "efficient_frontier": frontier_data,
            "portfolio_status": portfolio_status,
            "portfolio_copilot": portfolio_copilot,
            "portfolio_hedge_constructor": portfolio_hedge_constructor,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/report/single/create")
async def create_single_report(request: ReportRequest):
    try:
        if not request.result or not request.result.get("parametric_var"):
            raise ValueError("Single-asset calculation data is missing. Run the calculation first.")
        pdf_bytes = build_single_asset_report(request.calculation, request.result, request.chart_images or {})
        report_id = report_store.save("single-asset-risk-report.pdf", pdf_bytes)
        return {
            "report_id": report_id,
            "filename": "single-asset-risk-report.pdf",
            "download_url": f"/api/report/download/{report_id}",
            "message": "Отчёт сформирован и готов к скачиванию.",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/report/portfolio/create")
async def create_portfolio_report(request: ReportRequest):
    try:
        if not request.result or not request.result.get("portfolio_metrics"):
            raise ValueError("Portfolio calculation data is missing. Run the calculation first.")
        pdf_bytes = build_portfolio_report(request.calculation, request.result, request.chart_images or {})
        report_id = report_store.save("portfolio-risk-report.pdf", pdf_bytes)
        return {
            "report_id": report_id,
            "filename": "portfolio-risk-report.pdf",
            "download_url": f"/api/report/download/{report_id}",
            "message": "Отчёт сформирован и готов к скачиванию.",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/report/download/{report_id}")
async def download_report(report_id: str):
    report = report_store.get(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found or expired. Generate it again.")
    return Response(
        content=report.content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename=\"{report.filename}\"'},
    )


@app.post("/api/backtest")
async def run_backtest(request: BacktestRequest):
    try:
        history = rolling_historical_var_es(
            pnl=request.pnl,
            confidence=request.confidence,
            window=request.window,
        )
        
        alpha = 1.0 - request.confidence
        cc_test = christoffersen_conditional_coverage_test(list(history["exceptions"]), alpha)
        es_diag = es_realized_shortfall_diagnostics(
            realized_pnl=list(history["realized_pnl"]),
            var_pnl_thresholds=list(history["var_pnl_thresholds"]),
            es_losses=list(history["es_losses"]),
        )
        
        return {
            "rolling_history": history,
            "conditional_coverage_test": cc_test,
            "es_diagnostics": es_diag,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/risk_attribution")
async def run_risk_attribution(request: RiskAttributionRequest):
    try:
        result = delta_normal_var_contributions(
            factor_names=request.factor_names,
            delta_cash_values=request.delta_cash_values,
            mu_horizon_values=request.mu_horizon_values,
            covariance_horizon=request.covariance_horizon,
            z_value=request.z_value,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/stress_test")
async def run_stress_test(request: StressTestRequest):
    try:
        positions_dict = [p.dict() for p in request.positions]
        
        # Build standard scenarios
        underlying_ids = list(set(p.underlying_id for p in request.positions))
        standard_scenarios = build_standard_stress_scenarios(underlying_ids)
        
        results = []
        # Run standard scenarios
        for scenario in standard_scenarios:
            result = evaluate_full_revaluation_stress_scenario(
                positions=positions_dict,
                horizon_days=request.horizon_days,
                underlying_return_shocks=scenario['underlying_shocks'],
                volatility_shift=scenario['volatility_shift'],
                rate_shift=scenario['rate_shift'],
            )
            results.append({"name": scenario['name'], **result})

        # Run custom scenario from request
        custom_result = evaluate_full_revaluation_stress_scenario(
            positions=positions_dict,
            horizon_days=request.horizon_days,
            underlying_return_shocks=request.underlying_return_shocks,
            volatility_shift=request.volatility_shift,
            rate_shift=request.rate_shift,
        )
        results.append({"name": "Custom Scenario", **custom_result})
        
        return {"scenarios": results}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/moex/instruments")
async def get_moex_instruments(engine: str = "stock", market: str = "shares"):
    try:
        async with aiohttp.ClientSession() as session:
            instruments = await get_market_instruments(session, engine, market)
            return instruments
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/moex/option_board/{underlying_asset_code}")
async def get_moex_option_board(underlying_asset_code: str):
    try:
        async with aiohttp.ClientSession() as session:
            option_board = await get_option_board(session, underlying_asset_code)
            return option_board
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/moex/candles")
async def get_moex_candles(request: MoexCandlesRequest):
    try:
        async with aiohttp.ClientSession() as session:
            candles = await get_instrument_candles(
                session,
                request.secid,
                request.start_date,
                request.end_date,
                engine=request.engine,
                market=request.market,
            )
            return candles
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/option_pricing")
async def get_option_pricing(request: OptionPricingRequest):
    try:
        greeks = black_scholes_price_and_greeks(
            option_type=request.option_type,
            spot=request.spot,
            strike=request.strike,
            maturity_years=request.maturity_years,
            rate=request.rate,
            volatility=request.volatility,
            dividend_yield=request.dividend_yield,
        )
        return greeks
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/option_var")
async def get_option_var(request: OptionVaRRequest):
    try:
        seed_used = request.seed if request.seed is not None else random.SystemRandom().randrange(1, 2**32)

        # 1. Analytical Approximations
        approximations = option_var_moment_approximations(
            delta_cash=request.delta_cash,
            gamma_cash=request.gamma_cash,
            theta_horizon=request.theta_horizon,
            mu_horizon=request.mu_horizon,
            sigma_horizon=request.sigma_horizon,
            z_value=request.z_value,
        )

        # 2. Monte Carlo Simulation
        pnl_dg_mc = simulate_delta_gamma_pnl(
            delta_cash=request.delta_cash,
            gamma_cash=request.gamma_cash,
            theta_horizon=request.theta_horizon,
            mu_horizon=request.mu_horizon,
            sigma_horizon=request.sigma_horizon,
            simulations=request.simulations,
            seed=seed_used,
        )
        
        mc_var = historical_var_discrete(pnl_dg_mc, request.confidence)
        mc_es = expected_shortfall_discrete(pnl_dg_mc, request.confidence)

        full_revaluation = None
        if request.full_revaluation and request.full_revaluation_position is not None:
            fr_pnl = simulate_full_revaluation_pnl(
                positions=[request.full_revaluation_position.dict()],
                horizon_days=request.horizon_days,
                mu_horizon=request.mu_horizon,
                sigma_horizon=request.sigma_horizon,
                simulations=request.simulations,
                seed=seed_used,
                vol_mean_horizon=request.vol_mean_horizon,
                vol_sigma_horizon=request.vol_sigma_horizon,
                rate_mean_horizon=request.rate_mean_horizon,
                rate_sigma_horizon=request.rate_sigma_horizon,
            )
            fr_var = historical_var_discrete(fr_pnl, request.confidence)
            fr_es = expected_shortfall_discrete(fr_pnl, request.confidence)
            full_revaluation = {
                "pnl": fr_pnl,
                "var": fr_var["var_loss"],
                "es": fr_es["es_loss"],
                "var_details": fr_var,
                "es_details": fr_es,
            }

        return {
            "approximations": approximations,
            "pnl_dg_mc": pnl_dg_mc,
            "mc_var": mc_var["var_loss"],
            "mc_es": mc_es["es_loss"],
            "mc_var_details": mc_var,
            "mc_es_details": mc_es,
            "seed_used": seed_used,
            "seed_mode": "fixed" if request.seed is not None else "random",
            "full_revaluation": full_revaluation,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/forward_pricing")
async def get_forward_pricing(request: ForwardPricingRequest):
    try:
        result = price_linear_derivative(
            instrument_type=request.instrument_type,
            spot=request.spot,
            maturity_years=request.maturity_years,
            rate=request.rate,
            income_yield=request.income_yield,
            entry_price=request.entry_price,
            quantity=request.quantity,
            multiplier=request.multiplier,
            scenario_spot=request.scenario_spot,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/linear_var")
async def get_linear_var(request: LinearVaRRequest):
    try:
        return linear_derivative_var(
            instrument_type=request.instrument_type,
            spot=request.spot,
            quantity=request.quantity,
            multiplier=request.multiplier,
            confidence=request.confidence,
            horizon_days=request.horizon_days,
            mu_daily=request.mu_daily,
            sigma_daily=request.sigma_daily,
            historical_prices=request.historical_prices,
            scenario_move_pct=request.scenario_move_pct,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/bond_swap")
async def get_bond_swap_package(request: BondSwapRequest):
    try:
        return evaluate_bond_swap_package(
            issue=request.issue,
            curve=request.curve,
            valuation_date=request.valuation_date,
            rate_scenarios_1y=request.rate_scenarios_1y,
            hedge_ratios=request.hedge_ratios,
            include_full_issue_variant=request.include_full_issue_variant,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
