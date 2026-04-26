import math


def standard_normal_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def standard_normal_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def normalize_option_type(raw: str) -> str:
    text = raw.strip().lower()
    if text in {"c", "call", "колл", "к"}:
        return "call"
    if text in {"p", "put", "пут", "п"}:
        return "put"
    raise ValueError("Тип опциона должен быть call/c или put/p.")


def option_intrinsic_value(option_type: str, spot: float, strike: float) -> float:
    option = normalize_option_type(option_type)
    if option == "call":
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
    if spot <= 0:
        raise ValueError("Spot (S) должен быть > 0.")
    if strike <= 0:
        raise ValueError("Strike (K) должен быть > 0.")
    if maturity_years <= 0:
        raise ValueError("Время до экспирации (T) должно быть > 0.")
    if volatility <= 0:
        raise ValueError("Волатильность (sigma) должна быть > 0.")

    option = normalize_option_type(option_type)
    sqrt_t = math.sqrt(maturity_years)
    sigma_sqrt_t = volatility * sqrt_t
    d1 = (
        math.log(spot / strike)
        + (rate - dividend_yield + 0.5 * volatility * volatility) * maturity_years
    ) / sigma_sqrt_t
    d2 = d1 - sigma_sqrt_t

    n_d1 = standard_normal_cdf(d1)
    n_d2 = standard_normal_cdf(d2)
    phi_d1 = standard_normal_pdf(d1)
    disc_r = math.exp(-rate * maturity_years)
    disc_q = math.exp(-dividend_yield * maturity_years)

    if option == "call":
        price = spot * disc_q * n_d1 - strike * disc_r * n_d2
        delta = disc_q * n_d1
        theta = (
            -(spot * disc_q * phi_d1 * volatility) / (2.0 * sqrt_t)
            - rate * strike * disc_r * n_d2
            + dividend_yield * spot * disc_q * n_d1
        )
        rho = strike * maturity_years * disc_r * n_d2
    else:
        price = (
            strike * disc_r * standard_normal_cdf(-d2)
            - spot * disc_q * standard_normal_cdf(-d1)
        )
        delta = disc_q * (n_d1 - 1.0)
        theta = (
            -(spot * disc_q * phi_d1 * volatility) / (2.0 * sqrt_t)
            + rate * strike * disc_r * standard_normal_cdf(-d2)
            - dividend_yield * spot * disc_q * standard_normal_cdf(-d1)
        )
        rho = -strike * maturity_years * disc_r * standard_normal_cdf(-d2)

    gamma = disc_q * phi_d1 / (spot * sigma_sqrt_t)
    vega = spot * disc_q * phi_d1 * sqrt_t

    return {
        "d1": d1,
        "d2": d2,
        "price": price,
        "delta": delta,
        "gamma": gamma,
        "vega": vega,
        "vega_per_1pct": vega / 100.0,
        "theta": theta,
        "rho": rho,
        "rho_per_1pct": rho / 100.0,
    }
