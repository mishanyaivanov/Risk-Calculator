from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uvicorn
import os
import random
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
from services.portfolio_manager import calculate_portfolio_var, kupiec_pof_test, generate_efficient_frontier

app = FastAPI()
templates = Jinja2Templates(directory="templates")

class CalculationRequest(BaseModel):
    mode: str
    figi: Optional[str] = None
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

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/search")
async def search_instrument(query: str):
    token = os.getenv("TINKOFF_TOKEN")
    if not token:
        return [{"name": "Tinkoff Token Missing (Use Manual Mode)", "ticker": "ERROR", "figi": "", "type": "error"}]
        
    results = find_instruments(query, token)
    return results

@app.post("/api/calculate")
async def calculate_risk(request: CalculationRequest):
    prices = []
    candles_data = [] 
    
    try:
        if request.mode == 'tinkoff':
            token = os.getenv("TINKOFF_TOKEN")
            if not token:
                return {"error": "TINKOFF_TOKEN is not set. Please use Manual or Random mode."}
            
            if not request.figi:
                return {"error": "FIGI is required for Tinkoff mode."}
                
            candles = get_candles(request.figi, request.start_date, request.end_date, token)
            if not candles or len(candles) < 2:
                return {"error": "Not enough data from Tinkoff API (need at least 2 days)."}
            
            prices = [c['close'] for c in candles]
            candles_data = candles

        elif request.mode == 'manual':
            if not request.manual_prices:
                return {"error": "Please enter prices for Manual mode."}
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
            return {"error": "Invalid mode selected."}

        if len(prices) < 2:
             return {"error": "Not enough price data (need at least 2 prices)."}

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

        kupiec_result = kupiec_pof_test(pnl, [p_var.get("var_loss", 0)] * len(pnl), request.confidence)

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
            "backtest": kupiec_result,
            "pnl_series": pnl
        }

    except Exception as e:
        return {"error": str(e)}

@app.post("/api/calculate_portfolio")
async def calculate_portfolio(request: PortfolioRequest):
    token = os.getenv("TINKOFF_TOKEN")
    if not token:
        return {"error": "TINKOFF_TOKEN is required for portfolio calculation."}

    try:
        returns_list = []
        weights_list = []
        data_frames = []
        
        for item in request.items:
            candles = get_candles(item.figi, request.start_date, request.end_date, token)
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
            return {"error": "No valid data found for any instrument."}

        full_df = pd.concat(data_frames, axis=1, join='inner')
        full_df.dropna(inplace=True)
        
        if full_df.empty:
             return {"error": "No overlapping dates found for instruments."}

        returns_matrix = full_df.values
        weights_array = np.array(weights_list)
        
        if abs(weights_array.sum() - 1.0) > 0.01:
             weights_array = weights_array / weights_array.sum()

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
        
        return {
            "portfolio_metrics": portfolio_metrics,
            "correlation_matrix": full_df.corr().to_dict(),
            "dates": full_df.index.strftime('%Y-%m-%d').tolist(),
            "assets_cumulative_returns": assets_cum_returns.to_dict(),
            "portfolio_cumulative_return": portfolio_cum_return.tolist(),
            "efficient_frontier": frontier_data
        }

    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
