import math

from scipy.stats import norm


def normalize_option_type(option_type: str) -> str:
    normalized = option_type.strip().lower()
    if normalized in {"call", "c"}:
        return "call"
    if normalized in {"put", "p"}:
        return "put"
    raise ValueError(
        f"Unknown option type: {option_type}. Expected 'call'/'c' or 'put'/'p'."
    )


def option_intrinsic_value(option_type: str, spot: float, strike: float) -> float:
    normalized_type = normalize_option_type(option_type)
    if normalized_type == "call":
        return max(0.0, spot - strike)
    return max(0.0, strike - spot)


def black_scholes_price_and_greeks(
    option_type: str,
    spot: float,
    strike: float,
    maturity_years: float,
    rate: float,
    volatility: float,
    dividend_yield: float = 0.0,
) -> dict[str, float]:
    option_type = normalize_option_type(option_type)

    if maturity_years <= 0:
        intrinsic_value = option_intrinsic_value(option_type, spot, strike)
        return {
            "price": intrinsic_value,
            "delta": 0.0,
            "gamma": 0.0,
            "vega": 0.0,
            "theta": 0.0,
            "rho": 0.0,
            "d1": 0.0,
            "d2": 0.0,
        }

    if spot <= 0 or strike <= 0 or volatility <= 0:
        raise ValueError("Spot, strike, and volatility must be positive.")

    sqrt_t = math.sqrt(maturity_years)
    d1 = (
        math.log(spot / strike)
        + (rate - dividend_yield + 0.5 * volatility**2) * maturity_years
    ) / (volatility * sqrt_t)
    d2 = d1 - volatility * sqrt_t

    n_d1 = norm.pdf(d1)
    n_d1_cdf = norm.cdf(d1)
    n_d2_cdf = norm.cdf(d2)
    n_neg_d1_cdf = norm.cdf(-d1)
    n_neg_d2_cdf = norm.cdf(-d2)

    exp_minus_rt = math.exp(-rate * maturity_years)
    exp_minus_qt = math.exp(-dividend_yield * maturity_years)

    if option_type == "call":
        price = spot * exp_minus_qt * n_d1_cdf - strike * exp_minus_rt * n_d2_cdf
        delta = exp_minus_qt * n_d1_cdf
        gamma = exp_minus_qt * n_d1 / (spot * volatility * sqrt_t)
        vega = spot * exp_minus_qt * n_d1 * sqrt_t
        theta = (
            -(spot * exp_minus_qt * n_d1 * volatility) / (2 * sqrt_t)
            - rate * strike * exp_minus_rt * n_d2_cdf
            + dividend_yield * spot * exp_minus_qt * n_d1_cdf
        )
        rho = strike * maturity_years * exp_minus_rt * n_d2_cdf
    else:
        price = strike * exp_minus_rt * n_neg_d2_cdf - spot * exp_minus_qt * n_neg_d1_cdf
        delta = -exp_minus_qt * n_neg_d1_cdf
        gamma = exp_minus_qt * n_d1 / (spot * volatility * sqrt_t)
        vega = spot * exp_minus_qt * n_d1 * sqrt_t
        theta = (
            -(spot * exp_minus_qt * n_d1 * volatility) / (2 * sqrt_t)
            + rate * strike * exp_minus_rt * n_neg_d2_cdf
            - dividend_yield * spot * exp_minus_qt * n_neg_d1_cdf
        )
        rho = -strike * maturity_years * exp_minus_rt * n_neg_d2_cdf

    return {
        "price": price,
        "delta": delta,
        "gamma": gamma,
        "vega": vega,
        "vega_per_1pct": vega / 100.0,
        "theta": theta,
        "rho": rho,
        "rho_per_1pct": rho / 100.0,
        "d1": d1,
        "d2": d2,
    }
