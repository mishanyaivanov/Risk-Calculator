from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional
import uvicorn
import os
import random

from services.tinkoff_service import find_instruments, get_candles
from services.risk_calculator import (
    pnl_from_prices, 
    historical_var_discrete, 
    expected_shortfall_discrete, 
    parametric_var,
    parse_price_input,
    generate_random_prices
)

app = FastAPI()

# Mount static files (if needed in future)
# app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

class CalculationRequest(BaseModel):
    mode: str  # 'tinkoff', 'manual', 'random'
    figi: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    manual_prices: Optional[str] = None
    confidence: float = 0.95

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/search")
async def search_instrument(query: str):
    token = os.getenv("TINKOFF_TOKEN")
    if not token or token == "YourTokenHere":
        # Return empty list or mock data if no token, 
        # but for search specifically we need the API.
        # Let's return a message that token is missing but allow manual input.
        return [{"name": "Tinkoff Token Missing (Use Manual Mode)", "ticker": "ERROR", "figi": "", "type": "error"}]
        
    results = find_instruments(query, token)
    return results

@app.post("/api/calculate")
async def calculate_risk(request: CalculationRequest):
    prices = []
    
    try:
        if request.mode == 'tinkoff':
            token = os.getenv("TINKOFF_TOKEN")
            if not token or token == "YourTokenHere":
                return {"error": "TINKOFF_TOKEN is not set. Please use Manual or Random mode."}
            
            if not request.figi:
                return {"error": "FIGI is required for Tinkoff mode."}
                
            candles = get_candles(request.figi, request.start_date, request.end_date, token)
            if not candles or len(candles) < 2:
                return {"error": "Not enough data from Tinkoff API (need at least 2 days)."}
            prices = [c['close'] for c in candles]

        elif request.mode == 'manual':
            if not request.manual_prices:
                return {"error": "Please enter prices for Manual mode."}
            prices = parse_price_input(request.manual_prices)

        elif request.mode == 'random':
            prices = generate_random_prices(days=100)
        
        else:
            return {"error": "Invalid mode selected."}

        if len(prices) < 2:
             return {"error": "Not enough price data (need at least 2 prices)."}

        # Calculate P&L (assuming 1 unit position)
        pnl = pnl_from_prices(prices)

        # Calculate Risk Metrics
        h_var = historical_var_discrete(pnl, request.confidence)
        es = expected_shortfall_discrete(pnl, request.confidence)
        p_var = parametric_var(pnl, request.confidence)

        return {
            "prices": prices, # Added prices to response
            "prices_count": len(prices),
            "last_price": prices[-1],
            "historical_var": h_var,
            "es": es,
            "parametric_var": p_var
        }

    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
