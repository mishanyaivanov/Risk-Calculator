import math
from statistics import mean, stdev
from typing import Dict, List, Optional

from scipy.stats import norm

from .risk_calculator import (
    expected_shortfall_discrete,
    historical_var_discrete,
    normalize_confidence,
    pnl_from_prices,
    z_value_for_confidence,
)


def returns_from_prices(prices: List[float]) -> List[float]:
    if len(prices) < 2:
        return []

    returns: List[float] = []
    for previous, current in zip(prices[:-1], prices[1:]):
        if previous <= 0:
            raise ValueError("Historical prices must be positive to derive returns.")
        returns.append((current / previous) - 1.0)
    return returns


def rolling_horizon_pnl(single_day_pnl: List[float], horizon_days: int) -> List[float]:
    if horizon_days <= 0:
        raise ValueError("Horizon days must be positive.")
    if horizon_days == 1:
        return list(single_day_pnl)
    if len(single_day_pnl) < horizon_days:
        return []

    return [
        sum(single_day_pnl[index:index + horizon_days])
        for index in range(len(single_day_pnl) - horizon_days + 1)
    ]


def linear_derivative_var(
    spot: float,
    quantity: float = 1.0,
    multiplier: float = 1.0,
    confidence: float = 0.95,
    horizon_days: int = 1,
    mu_daily: Optional[float] = None,
    sigma_daily: Optional[float] = None,
    historical_prices: Optional[List[float]] = None,
    scenario_move_pct: Optional[float] = None,
    instrument_type: str = "linear_derivative",
) -> Dict[str, object]:
    if spot <= 0:
        raise ValueError("Spot price must be positive.")
    if multiplier == 0:
        raise ValueError("Multiplier must not be zero.")
    if horizon_days <= 0:
        raise ValueError("Horizon days must be positive.")

    confidence = normalize_confidence(confidence)
    exposure_cash = spot * quantity * multiplier

    derived_returns: List[float] = []
    historical_pnl: List[float] = []
    if historical_prices:
        if len(historical_prices) < 2:
            raise ValueError("Historical prices must contain at least two observations.")
        derived_returns = returns_from_prices(historical_prices)
        historical_pnl = rolling_horizon_pnl(
            pnl_from_prices(historical_prices, position_size=quantity * multiplier),
            horizon_days=horizon_days,
        )

    effective_mu_daily = mu_daily
    effective_sigma_daily = sigma_daily
    if derived_returns:
        if effective_mu_daily is None:
            effective_mu_daily = mean(derived_returns)
        if effective_sigma_daily is None:
            effective_sigma_daily = stdev(derived_returns) if len(derived_returns) > 1 else 0.0

    parametric = None
    if effective_mu_daily is not None and effective_sigma_daily is not None:
        mu_horizon = effective_mu_daily * horizon_days
        sigma_horizon = effective_sigma_daily * math.sqrt(horizon_days)
        z_value = z_value_for_confidence(confidence)
        pnl_mu = exposure_cash * mu_horizon
        pnl_sigma = abs(exposure_cash) * sigma_horizon
        q_alpha_pnl = pnl_mu - z_value * pnl_sigma
        alpha = 1.0 - confidence
        tail_multiplier = norm.pdf(z_value) / alpha
        es_pnl = pnl_mu - pnl_sigma * tail_multiplier

        parametric = {
            "mu_daily": effective_mu_daily,
            "sigma_daily": effective_sigma_daily,
            "mu_horizon": mu_horizon,
            "sigma_horizon": sigma_horizon,
            "pnl_mu": pnl_mu,
            "pnl_sigma": pnl_sigma,
            "q_alpha_pnl": q_alpha_pnl,
            "var_loss": max(0.0, -q_alpha_pnl),
            "es_loss": max(0.0, -es_pnl),
            "z_value": z_value,
        }

    historical = None
    if historical_pnl:
        historical = {
            "observations": len(historical_pnl),
            "var": historical_var_discrete(historical_pnl, confidence),
            "es": expected_shortfall_discrete(historical_pnl, confidence),
        }

    scenario = None
    if scenario_move_pct is not None:
        scenario = {
            "move_pct": scenario_move_pct,
            "pnl": exposure_cash * scenario_move_pct,
        }

    return {
        "instrument_type": instrument_type,
        "spot": spot,
        "quantity": quantity,
        "multiplier": multiplier,
        "confidence": confidence,
        "horizon_days": horizon_days,
        "exposure_cash": exposure_cash,
        "historical_prices_count": len(historical_prices or []),
        "parametric": parametric,
        "historical": historical,
        "scenario": scenario,
    }
