import math
import random
from statistics import mean, stdev
from typing import List, Tuple, Optional

# --- Helper Functions ---

def parse_price_input(raw_input: str) -> List[float]:
    """Parses a string of numbers separated by spaces or commas."""
    # Заменяем запятые на точки (для десятичных дробей) если они используются как разделитель, 
    # но тут сложный момент с локалью. 
    # Давайте считать, что разделитель чисел - пробел, а точка - десятичный разделитель.
    # Если пользователь ввел через запятую как разделитель списка:
    cleaned = raw_input.replace(",", " ")
    try:
        return [float(x) for x in cleaned.split() if x.strip()]
    except ValueError:
        raise ValueError("Input contains non-numeric values.")

def generate_random_prices(days: int = 100, start_price: float = 100.0, volatility: float = 0.02) -> List[float]:
    """Generates a random walk price series (Geometric Brownian Motion simplified)."""
    prices = [start_price]
    for _ in range(days):
        # Random percentage change
        change_pct = random.gauss(0, volatility)
        new_price = prices[-1] * (1 + change_pct)
        prices.append(max(0.01, new_price)) # Price cannot be negative
    return prices

# --- Existing Logic ---

Z_BY_CONFIDENCE = {
    0.95: 1.645,
    0.99: 2.326,
}

def normalize_confidence(value: float) -> float:
    if value > 1:
        value = value / 100.0
    value = round(value, 4)
    if value not in Z_BY_CONFIDENCE:
        # Fallback to nearest or default if needed, but raising error is safer for risk calc
        # For this web app, let's default to 0.95 if invalid to avoid crashing
        return 0.95 
    return value

def z_value_for_confidence(confidence: float) -> float:
    return Z_BY_CONFIDENCE.get(confidence, 1.645)

def pnl_from_prices(prices: List[float], position_size: float = 1.0) -> List[float]:
    if len(prices) < 2:
        # Если цен мало, возвращаем пустой список или ошибку, обработаем выше
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
