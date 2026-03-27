import math
from typing import Dict, Optional


SUPPORTED_LINEAR_DERIVATIVES = {"futures", "future", "forward", "spfi"}


def normalize_linear_derivative_type(instrument_type: str) -> str:
    normalized = instrument_type.strip().lower()
    if normalized not in SUPPORTED_LINEAR_DERIVATIVES:
        raise ValueError(
            "Unknown derivative type. Expected one of: futures, forward, spfi."
        )
    if normalized == "future":
        return "futures"
    return normalized


def theoretical_forward_price(
    spot: float,
    maturity_years: float,
    rate: float,
    income_yield: float = 0.0,
) -> float:
    if spot <= 0:
        raise ValueError("Spot price must be positive.")
    if maturity_years < 0:
        raise ValueError("Maturity must be non-negative.")
    return spot * math.exp((rate - income_yield) * maturity_years)


def price_linear_derivative(
    instrument_type: str,
    spot: float,
    maturity_years: float,
    rate: float,
    income_yield: float = 0.0,
    entry_price: Optional[float] = None,
    quantity: float = 1.0,
    multiplier: float = 1.0,
    scenario_spot: Optional[float] = None,
) -> Dict[str, float | str | None]:
    derivative_type = normalize_linear_derivative_type(instrument_type)
    if multiplier == 0:
        raise ValueError("Multiplier must not be zero.")

    fair_price = theoretical_forward_price(
        spot=spot,
        maturity_years=maturity_years,
        rate=rate,
        income_yield=income_yield,
    )
    discount_factor = math.exp(-rate * maturity_years)
    scale = quantity * multiplier

    current_value = None
    current_value_pv = None
    pnl_vs_entry = None
    if entry_price is not None:
        pnl_vs_entry = (fair_price - entry_price) * scale
        current_value = pnl_vs_entry
        current_value_pv = pnl_vs_entry * discount_factor

    scenario_fair_price = None
    scenario_pnl_vs_entry = None
    if scenario_spot is not None:
        scenario_fair_price = theoretical_forward_price(
            spot=scenario_spot,
            maturity_years=maturity_years,
            rate=rate,
            income_yield=income_yield,
        )
        if entry_price is not None:
            scenario_pnl_vs_entry = (scenario_fair_price - entry_price) * scale

    return {
        "instrument_type": derivative_type,
        "spot": spot,
        "maturity_years": maturity_years,
        "rate": rate,
        "income_yield": income_yield,
        "fair_price": fair_price,
        "carry": fair_price - spot,
        "discount_factor": discount_factor,
        "quantity": quantity,
        "multiplier": multiplier,
        "position_notional": fair_price * scale,
        "entry_price": entry_price,
        "current_value": current_value,
        "current_value_pv": current_value_pv,
        "pnl_vs_entry": pnl_vs_entry,
        "scenario_spot": scenario_spot,
        "scenario_fair_price": scenario_fair_price,
        "scenario_pnl_vs_entry": scenario_pnl_vs_entry,
    }
