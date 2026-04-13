import math
import random
from statistics import mean, stdev
from typing import List

from scipy.stats import norm

def parse_price_input(raw_input: str) -> List[float]:
    """Parses a string of numbers separated by spaces or commas."""
    cleaned = raw_input.replace(",", " ")
    try:
        return [float(x) for x in cleaned.split() if x.strip()]
    except ValueError:
        raise ValueError("Input contains non-numeric values.")

def generate_random_prices(days: int = 100, start_price: float = 100.0, volatility: float = 0.02) -> List[float]:
    """Generates a random walk price series (Geometric Brownian Motion simplified)."""
    prices = [start_price]
    for _ in range(days):
        change_pct = random.gauss(0, volatility)
        new_price = prices[-1] * (1 + change_pct)
        prices.append(max(0.01, new_price)) 
    return prices

def normalize_confidence(value: float) -> float:
    if value > 1:
        value = value / 100.0
    if value <= 0.0 or value >= 1.0:
        raise ValueError("Confidence must lie between 0 and 1, or between 0 and 100 when provided as a percent.")
    return float(value)

def z_value_for_confidence(confidence: float) -> float:
    normalized_confidence = normalize_confidence(confidence)
    return float(norm.ppf(normalized_confidence))

def pnl_from_prices(prices: List[float], position_size: float = 1.0) -> List[float]:
    if len(prices) < 2:
        return []
    return [position_size * (prices[i] - prices[i - 1]) for i in range(1, len(prices))]

def historical_var_discrete(pnl: List[float], confidence: float) -> dict:
    if len(pnl) < 2:
        return {"error": "Not enough data"}
    
    confidence = normalize_confidence(confidence)
    alpha = 1.0 - confidence
    sorted_pnl = sorted(pnl)
    n = len(sorted_pnl)
    k = max(1, math.ceil(n * alpha))
    var_pnl = sorted_pnl[k - 1]
    var_loss = max(0.0, -var_pnl)
    
    return {
        "var_loss": var_loss,
        "var_pnl": var_pnl,
        "k": k,
        "confidence": confidence
    }

def expected_shortfall_discrete(pnl: List[float], confidence: float) -> dict:
    if len(pnl) < 2:
        return {"error": "Not enough data"}

    confidence = normalize_confidence(confidence)
    alpha = 1.0 - confidence
    sorted_pnl = sorted(pnl)
    n = len(sorted_pnl)
    tail_count = max(1, math.ceil(n * alpha))
    tail = sorted_pnl[:tail_count]
    es_pnl = sum(tail) / tail_count
    es_loss = max(0.0, -es_pnl)

    return {
        "es_loss": es_loss,
        "es_pnl": es_pnl,
        "tail_count": tail_count
    }

def parametric_var(pnl: List[float], confidence: float) -> dict:
    if len(pnl) < 2:
        return {"error": "Not enough data"}

    confidence = normalize_confidence(confidence)
    mu = mean(pnl)
    sigma = stdev(pnl)
    z = z_value_for_confidence(confidence)
    q_alpha_pnl = mu - z * sigma
    var_loss = max(0.0, -q_alpha_pnl)

    return {
        "var_loss": var_loss,
        "q_alpha_pnl": q_alpha_pnl,
        "mu": mu,
        "sigma": sigma,
        "z_value": z
    }

def normal_liquidation_cost(mid_market_value: float, spread_percent: float) -> float:
    """Calculates liquidation cost under normal market conditions."""
    return 0.5 * abs(mid_market_value) * (spread_percent / 100.0)

def stressed_liquidation_cost(
    mid_market_value: float,
    spread_percent: float,
    confidence: float,
    sigma_spread_percent: float,
) -> float:
    """Calculates liquidation cost under stressed market conditions."""
    z = z_value_for_confidence(confidence)
    s = spread_percent / 100.0
    sigma_s = sigma_spread_percent / 100.0
    return 0.5 * abs(mid_market_value) * (s + z * sigma_s)

def linear_unwind_adjustment_factor(days: int) -> float:
    if days <= 0:
        raise ValueError("Liquidation period T must be > 0.")
    return math.sqrt(((1 + days) * (1 + 2 * days)) / (6 * days))

def linear_unwind_adjusted_var(base_var: float, days: int) -> float:
    """Adjusts VaR for linear liquidation over T days."""
    factor = linear_unwind_adjustment_factor(days)
    return base_var / factor
