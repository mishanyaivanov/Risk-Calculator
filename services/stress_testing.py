from typing import List, Dict, Union
from .option_pricing import black_scholes_price_and_greeks, option_intrinsic_value, normalize_option_type

def evaluate_full_revaluation_stress_scenario(
    positions: list[dict[str, float | str]],
    horizon_days: int,
    underlying_return_shocks: dict[str, float],
    volatility_shift: float = 0.0,
    rate_shift: float = 0.0,
) -> dict[str, float | list[dict[str, int | float | str]]]:
    if horizon_days <= 0:
        raise ValueError("Stress scenario horizon must be greater than 0 days.")
    if not positions:
        raise ValueError("At least one position is required.")

    horizon_years = horizon_days / 365.0
    total_pnl = 0.0
    total_base_value = 0.0
    position_rows: list[dict[str, int | float | str]] = []

    for idx, position in enumerate(positions, start=1):
        option_type = normalize_option_type(str(position["option_type"]))
        spot0 = float(position["spot"])
        strike = float(position["strike"])
        maturity_years = float(position["maturity_years"])
        rate0 = float(position["rate"])
        sigma0 = float(position["volatility"])
        dividend = float(position["dividend_yield"])
        scale = float(position["quantity"]) * float(position.get("multiplier", 1.0))
        underlying_id = str(position.get("underlying_id", "U1"))

        if underlying_id not in underlying_return_shocks:
            raise ValueError(
                f"Stress scenario is missing a return shock for underlying '{underlying_id}'."
            )
        return_shock = underlying_return_shocks[underlying_id]
        spot_scenario = max(1e-12, spot0 * (1.0 + return_shock))
        maturity_remaining = maturity_years - horizon_years
        rate_scenario = rate0 + rate_shift
        sigma_scenario = max(1e-8, sigma0 + volatility_shift)

        base_price = black_scholes_price_and_greeks(
            option_type=option_type,
            spot=spot0,
            strike=strike,
            maturity_years=maturity_years,
            rate=rate0,
            volatility=sigma0,
            dividend_yield=dividend,
        )["price"]
        
        if maturity_remaining > 0:
            stressed_price = black_scholes_price_and_greeks(
                option_type=option_type,
                spot=spot_scenario,
                strike=strike,
                maturity_years=maturity_remaining,
                rate=rate_scenario,
                volatility=sigma_scenario,
                dividend_yield=dividend,
            )["price"]
        else:
            # If maturity is reached or passed, use intrinsic value
            stressed_price = option_intrinsic_value(
                option_type=option_type,
                spot=spot_scenario,
                strike=strike,
            )

        base_value = scale * base_price
        stressed_value = scale * stressed_price
        pnl = stressed_value - base_value
        total_pnl += pnl
        total_base_value += base_value

        position_rows.append(
            {
                "position_index": idx,
                "underlying_id": underlying_id,
                "return_shock": return_shock,
                "base_value": base_value,
                "stressed_value": stressed_value,
                "pnl": pnl,
            }
        )

    return {
        "base_value": total_base_value,
        "stressed_value": total_base_value + total_pnl,
        "total_pnl": total_pnl,
        "positions": position_rows,
    }


def build_standard_stress_scenarios(
    underlying_ids: list[str],
) -> list[dict[str, float | str | dict[str, float]]]:
    if not underlying_ids:
        raise ValueError("Underlying list must not be empty.")

    def uniform_shock(value: float) -> dict[str, float]:
        return {name: value for name in underlying_ids}

    return [
        {
            "name": "Market -10%",
            "underlying_shocks": uniform_shock(-0.10),
            "volatility_shift": 0.0,
            "rate_shift": 0.0,
        },
        {
            "name": "Market -20%",
            "underlying_shocks": uniform_shock(-0.20),
            "volatility_shift": 0.0,
            "rate_shift": 0.0,
        },
        {
            "name": "Crash -15% + Vol +10pp",
            "underlying_shocks": uniform_shock(-0.15),
            "volatility_shift": 0.10,
            "rate_shift": 0.0,
        },
        {
            "name": "Rates +100 bps",
            "underlying_shocks": uniform_shock(0.0),
            "volatility_shift": 0.0,
            "rate_shift": 0.01,
        },
        {
            "name": "Rates -100 bps",
            "underlying_shocks": uniform_shock(0.0),
            "volatility_shift": 0.0,
            "rate_shift": -0.01,
        },
    ]



