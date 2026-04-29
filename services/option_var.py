import math
from typing import Any

import numpy as np

from .option_pricing import (
    black_scholes_price_and_greeks,
    normalize_option_type,
    option_intrinsic_value,
)


def validate_correlation_matrix(correlation_matrix: list[list[float]], tol: float = 1e-10) -> None:
    n = len(correlation_matrix)
    if n == 0:
        raise ValueError("Correlation matrix must not be empty.")
    for i, row in enumerate(correlation_matrix):
        if len(row) != n:
            raise ValueError("Correlation matrix must be square.")
        if abs(row[i] - 1.0) > tol:
            raise ValueError("Correlation matrix diagonal must equal 1.")

    for i, row in enumerate(correlation_matrix):
        for j, value in enumerate(row):
            if value < -1.0 - tol or value > 1.0 + tol:
                raise ValueError("Correlations must stay within [-1, 1].")
            if abs(value - correlation_matrix[j][i]) > tol:
                raise ValueError("Correlation matrix must be symmetric.")


def _semi_cholesky(covariance_matrix: list[list[float]], tol: float = 1e-12) -> list[list[float]]:
    n = len(covariance_matrix)
    if n == 0:
        raise ValueError("Covariance matrix must not be empty.")
    for row in covariance_matrix:
        if len(row) != n:
            raise ValueError("Covariance matrix must be square.")

    lower = [[0.0 for _ in range(n)] for _ in range(n)]
    for i in range(n):
        for j in range(i + 1):
            value = covariance_matrix[i][j] - sum(lower[i][k] * lower[j][k] for k in range(j))
            if i == j:
                if value < -tol:
                    raise ValueError("Covariance matrix must be positive semidefinite.")
                lower[i][j] = math.sqrt(max(0.0, value))
            else:
                if abs(lower[j][j]) <= tol:
                    if abs(value) > tol:
                        raise ValueError("Covariance matrix must be positive semidefinite.")
                    lower[i][j] = 0.0
                else:
                    lower[i][j] = value / lower[j][j]
    return lower


def validate_covariance_matrix(covariance_matrix: list[list[float]], tol: float = 1e-10) -> None:
    n = len(covariance_matrix)
    if n == 0:
        raise ValueError("Covariance matrix must not be empty.")
    for i, row in enumerate(covariance_matrix):
        if len(row) != n:
            raise ValueError("Covariance matrix must be square.")
        if row[i] < -tol:
            raise ValueError("Covariance matrix diagonal cannot be negative.")
        for j, value in enumerate(row):
            if abs(value - covariance_matrix[j][i]) > tol:
                raise ValueError("Covariance matrix must be symmetric.")
    _semi_cholesky(covariance_matrix, tol=tol)


def gamma_matrix_from_diagonal(gamma_cash_values: list[float]) -> list[list[float]]:
    n = len(gamma_cash_values)
    return [
        [gamma_cash_values[i] if i == j else 0.0 for j in range(n)]
        for i in range(n)
    ]


def _validate_gamma_matrix(gamma_matrix: list[list[float]], expected_size: int, tol: float = 1e-10) -> None:
    if len(gamma_matrix) != expected_size:
        raise ValueError("Gamma matrix size does not match the number of factors.")
    for i, row in enumerate(gamma_matrix):
        if len(row) != expected_size:
            raise ValueError("Gamma matrix must be square.")
        for j, value in enumerate(row):
            if abs(value - gamma_matrix[j][i]) > tol:
                raise ValueError("Gamma matrix must be symmetric.")


def _mat_vec(matrix: list[list[float]], vector: list[float]) -> list[float]:
    return [sum(row[j] * vector[j] for j in range(len(vector))) for row in matrix]


def _quadratic_form(vector: list[float], matrix: list[list[float]]) -> float:
    matrix_times_vector = _mat_vec(matrix, vector)
    return sum(vector[i] * matrix_times_vector[i] for i in range(len(vector)))


def _trace_product(left: list[list[float]], right: list[list[float]]) -> float:
    n = len(left)
    total = 0.0
    for i in range(n):
        for j in range(n):
            total += left[i][j] * right[j][i]
    return total


def _mat_mul(left: list[list[float]], right: list[list[float]]) -> list[list[float]]:
    n = len(left)
    return [
        [sum(left[i][k] * right[k][j] for k in range(n)) for j in range(n)]
        for i in range(n)
    ]


def covariance_from_sigmas_and_correlation(
    sigma_values: list[float],
    correlation_matrix: list[list[float]],
) -> list[list[float]]:
    n = len(sigma_values)
    if n == 0:
        raise ValueError("At least one risk factor is required.")
    if len(correlation_matrix) != n:
        raise ValueError("Correlation matrix size does not match sigma values.")
    validate_correlation_matrix(correlation_matrix)

    covariance = [[0.0 for _ in range(n)] for _ in range(n)]
    for i in range(n):
        if sigma_values[i] < 0:
            raise ValueError("Sigma values cannot be negative.")
        for j in range(n):
            covariance[i][j] = correlation_matrix[i][j] * sigma_values[i] * sigma_values[j]
    validate_covariance_matrix(covariance)
    return covariance


def option_var_moment_approximations(
    delta_cash: float,
    gamma_cash: float,
    theta_horizon: float,
    mu_horizon: float,
    sigma_horizon: float,
    z_value: float,
) -> dict[str, float]:
    mu_dn = delta_cash * mu_horizon + theta_horizon
    sigma_dn = abs(delta_cash) * sigma_horizon
    q_dn = mu_dn - z_value * sigma_dn
    var_dn = max(0.0, -q_dn)

    mu_dg = (
        delta_cash * mu_horizon
        + 0.5 * gamma_cash * (mu_horizon**2 + sigma_horizon**2)
        + theta_horizon
    )
    variance_dg = (
        sigma_horizon**2 * (delta_cash + gamma_cash * mu_horizon) ** 2
        + 0.5 * gamma_cash**2 * sigma_horizon**4
    )
    sigma_dg = math.sqrt(max(0.0, variance_dg))
    q_dg = mu_dg - z_value * sigma_dg
    var_dg = max(0.0, -q_dg)

    return {
        "mu_dn": mu_dn,
        "sigma_dn": sigma_dn,
        "q_dn": q_dn,
        "var_dn": var_dn,
        "mu_dg": mu_dg,
        "sigma_dg": sigma_dg,
        "q_dg": q_dg,
        "var_dg": var_dg,
    }


def option_var_moment_approximations_multifactor(
    delta_cash_values: list[float],
    gamma_cash_values: list[float],
    theta_horizon: float,
    mu_horizon_values: list[float],
    covariance_horizon: list[list[float]],
    z_value: float,
    gamma_cross_matrix: list[list[float]] | None = None,
) -> dict[str, float]:
    n = len(delta_cash_values)
    if (
        len(gamma_cash_values) != n
        or len(mu_horizon_values) != n
        or len(covariance_horizon) != n
    ):
        raise ValueError("Multifactor Delta-Gamma inputs must have matching dimensions.")
    for row in covariance_horizon:
        if len(row) != n:
            raise ValueError("Covariance matrix must be square.")
    validate_covariance_matrix(covariance_horizon)

    gamma_matrix = gamma_cross_matrix or gamma_matrix_from_diagonal(gamma_cash_values)
    _validate_gamma_matrix(gamma_matrix, n)

    mu_dn = theta_horizon + sum(
        delta_cash_values[i] * mu_horizon_values[i] for i in range(n)
    )
    var_dn = 0.0
    for i in range(n):
        for j in range(n):
            var_dn += delta_cash_values[i] * covariance_horizon[i][j] * delta_cash_values[j]
    sigma_dn = math.sqrt(max(0.0, var_dn))
    q_dn = mu_dn - z_value * sigma_dn
    var_dn_loss = max(0.0, -q_dn)

    mu_dg = mu_dn
    for i in range(n):
        for j in range(n):
            mu_dg += 0.5 * gamma_matrix[i][j] * (
                covariance_horizon[i][j] + mu_horizon_values[i] * mu_horizon_values[j]
            )

    gamma_sigma = _mat_mul(gamma_matrix, covariance_horizon)
    sigma_gamma = _mat_mul(covariance_horizon, gamma_matrix)
    gamma_sigma_gamma = _mat_mul(gamma_matrix, sigma_gamma)
    cov_l_q = sum(
        delta_cash_values[i] * sigma_gamma[i][j] * mu_horizon_values[j]
        for i in range(n)
        for j in range(n)
    )
    var_q = 0.5 * _trace_product(gamma_sigma, gamma_sigma)
    var_q += _quadratic_form(mu_horizon_values, gamma_sigma_gamma)

    var_dg_total = max(0.0, var_dn + var_q + 2.0 * cov_l_q)
    sigma_dg = math.sqrt(var_dg_total)
    q_dg = mu_dg - z_value * sigma_dg
    var_dg_loss = max(0.0, -q_dg)

    return {
        "mu_dn": mu_dn,
        "sigma_dn": sigma_dn,
        "q_dn": q_dn,
        "var_dn": var_dn_loss,
        "mu_dg": mu_dg,
        "sigma_dg": sigma_dg,
        "q_dg": q_dg,
        "var_dg": var_dg_loss,
    }


def simulate_delta_gamma_pnl(
    delta_cash: float,
    gamma_cash: float,
    theta_horizon: float,
    mu_horizon: float,
    sigma_horizon: float,
    simulations: int,
    seed: int | None,
) -> list[float]:
    if simulations < 2:
        raise ValueError("The number of simulations must be at least 2.")
    if sigma_horizon < 0:
        raise ValueError("Sigma horizon cannot be negative.")

    rng = np.random.default_rng(seed)
    shocks = rng.normal(loc=mu_horizon, scale=sigma_horizon, size=simulations)
    pnl = delta_cash * shocks + 0.5 * gamma_cash * shocks**2 + theta_horizon
    return pnl.tolist()


def simulate_delta_gamma_pnl_multifactor(
    delta_cash_values: list[float],
    gamma_cash_values: list[float],
    theta_horizon: float,
    mean_vector: list[float],
    covariance_matrix: list[list[float]],
    simulations: int,
    seed: int | None,
    gamma_cross_matrix: list[list[float]] | None = None,
) -> list[float]:
    n = len(delta_cash_values)
    if len(gamma_cash_values) != n or len(mean_vector) != n:
        raise ValueError("Multifactor Delta-Gamma vectors must have matching dimensions.")
    validate_covariance_matrix(covariance_matrix)
    gamma_matrix = gamma_cross_matrix or gamma_matrix_from_diagonal(gamma_cash_values)
    _validate_gamma_matrix(gamma_matrix, n)

    rng = np.random.default_rng(seed)
    scenarios = rng.multivariate_normal(mean=mean_vector, cov=covariance_matrix, size=simulations)
    pnl = []
    for scenario in scenarios:
        pnl_value = theta_horizon
        for i in range(n):
            pnl_value += delta_cash_values[i] * scenario[i]
            for j in range(n):
                pnl_value += 0.5 * gamma_matrix[i][j] * scenario[i] * scenario[j]
        pnl.append(float(pnl_value))
    return pnl


def simulate_full_revaluation_pnl(
    positions: list[dict[str, Any]],
    horizon_days: int,
    mu_horizon: float,
    sigma_horizon: float,
    simulations: int,
    seed: int | None,
    vol_mean_horizon: float,
    vol_sigma_horizon: float,
    rate_mean_horizon: float,
    rate_sigma_horizon: float,
) -> list[float]:
    return simulate_full_revaluation_pnl_multifactor(
        positions=positions,
        horizon_days=horizon_days,
        underlying_order=["U1"],
        mean_vector=[mu_horizon],
        covariance_matrix=[[sigma_horizon**2]],
        simulations=simulations,
        seed=seed,
        vol_mean_horizon=vol_mean_horizon,
        vol_sigma_horizon=vol_sigma_horizon,
        rate_mean_horizon=rate_mean_horizon,
        rate_sigma_horizon=rate_sigma_horizon,
    )


def simulate_full_revaluation_pnl_multifactor(
    positions: list[dict[str, Any]],
    horizon_days: int,
    underlying_order: list[str],
    mean_vector: list[float],
    covariance_matrix: list[list[float]],
    simulations: int,
    seed: int | None,
    vol_mean_horizon: float,
    vol_sigma_horizon: float,
    rate_mean_horizon: float,
    rate_sigma_horizon: float,
) -> list[float]:
    if horizon_days <= 0:
        raise ValueError("Horizon must be positive.")
    if not underlying_order:
        raise ValueError("At least one underlying factor is required.")
    if len(underlying_order) != len(mean_vector):
        raise ValueError("Underlying order and mean vector must have matching dimensions.")
    validate_covariance_matrix(covariance_matrix)

    rng = np.random.default_rng(seed)
    scenarios = rng.multivariate_normal(mean=mean_vector, cov=covariance_matrix, size=simulations)
    vol_shocks = rng.normal(loc=vol_mean_horizon, scale=vol_sigma_horizon, size=simulations)
    rate_shocks = rng.normal(loc=rate_mean_horizon, scale=rate_sigma_horizon, size=simulations)

    horizon_years = horizon_days / 365.0
    underlying_index = {name: idx for idx, name in enumerate(underlying_order)}
    base_prices = []
    for position in positions:
        base_prices.append(
            black_scholes_price_and_greeks(
                option_type=str(position["option_type"]),
                spot=float(position["spot"]),
                strike=float(position["strike"]),
                maturity_years=float(position["maturity_years"]),
                rate=float(position["rate"]),
                volatility=float(position["volatility"]),
                dividend_yield=float(position.get("dividend_yield", 0.0)),
            )["price"]
        )

    pnl = []
    for scenario_idx, scenario in enumerate(scenarios):
        total_pnl = 0.0
        for position_idx, position in enumerate(positions):
            option_type = normalize_option_type(str(position["option_type"]))
            spot0 = float(position["spot"])
            strike = float(position["strike"])
            maturity_years = float(position["maturity_years"])
            rate0 = float(position["rate"])
            sigma0 = float(position["volatility"])
            dividend_yield = float(position.get("dividend_yield", 0.0))
            scale = float(position["quantity"]) * float(position.get("multiplier", 1.0))
            underlying_id = str(position.get("underlying_id", "U1"))

            if underlying_id not in underlying_index:
                raise ValueError(f"Underlying '{underlying_id}' is missing from underlying_order.")

            shock = float(scenario[underlying_index[underlying_id]])
            spot_scenario = max(1e-12, spot0 * (1.0 + shock))
            remaining_maturity = maturity_years - horizon_years
            rate_scenario = rate0 + float(rate_shocks[scenario_idx])
            sigma_scenario = max(1e-8, sigma0 + float(vol_shocks[scenario_idx]))

            if remaining_maturity > 0:
                scenario_price = black_scholes_price_and_greeks(
                    option_type=option_type,
                    spot=spot_scenario,
                    strike=strike,
                    maturity_years=remaining_maturity,
                    rate=rate_scenario,
                    volatility=sigma_scenario,
                    dividend_yield=dividend_yield,
                )["price"]
            else:
                scenario_price = option_intrinsic_value(
                    option_type=option_type,
                    spot=spot_scenario,
                    strike=strike,
                )

            total_pnl += scale * (scenario_price - base_prices[position_idx])
        pnl.append(float(total_pnl))
    return pnl
