import math
import random

from .option_pricing import (
    black_scholes_price_and_greeks,
    normalize_option_type,
    option_intrinsic_value,
)


def validate_correlation_matrix(correlation_matrix: list[list[float]], tol: float = 1e-10) -> None:
    n = len(correlation_matrix)
    if n == 0:
        raise ValueError("Correlation matrix не может быть пустой.")
    for i, row in enumerate(correlation_matrix):
        if len(row) != n:
            raise ValueError("Correlation matrix должна быть квадратной.")
        if abs(row[i] - 1.0) > tol:
            raise ValueError("Диагональ correlation matrix должна быть равна 1.")

    for i, row in enumerate(correlation_matrix):
        for j, value in enumerate(row):
            if value < -1.0 - tol or value > 1.0 + tol:
                raise ValueError("Корреляции должны быть в диапазоне [-1, 1].")
            if abs(value - correlation_matrix[j][i]) > tol:
                raise ValueError("Correlation matrix должна быть симметричной.")


def validate_covariance_matrix(covariance_matrix: list[list[float]], tol: float = 1e-10) -> None:
    n = len(covariance_matrix)
    if n == 0:
        raise ValueError("Covariance matrix не может быть пустой.")
    for i, row in enumerate(covariance_matrix):
        if len(row) != n:
            raise ValueError("Covariance matrix должна быть квадратной.")
        if row[i] < -tol:
            raise ValueError("Диагональ covariance matrix не может быть отрицательной.")
        for j, value in enumerate(row):
            if abs(value - covariance_matrix[j][i]) > tol:
                raise ValueError("Covariance matrix должна быть симметричной.")

    _semi_cholesky(covariance_matrix, tol=tol)


def gamma_matrix_from_diagonal(gamma_cash_values: list[float]) -> list[list[float]]:
    n = len(gamma_cash_values)
    return [
        [gamma_cash_values[i] if i == j else 0.0 for j in range(n)]
        for i in range(n)
    ]


def _validate_gamma_matrix(gamma_matrix: list[list[float]], expected_size: int, tol: float = 1e-10) -> None:
    if len(gamma_matrix) != expected_size:
        raise ValueError("Размер gamma matrix не совпадает с количеством факторов.")
    for i, row in enumerate(gamma_matrix):
        if len(row) != expected_size:
            raise ValueError("Gamma matrix должна быть квадратной.")
        for j, value in enumerate(row):
            if abs(value - gamma_matrix[j][i]) > tol:
                raise ValueError("Gamma matrix должна быть симметричной.")


def _mat_vec(matrix: list[list[float]], vector: list[float]) -> list[float]:
    return [sum(row[j] * vector[j] for j in range(len(vector))) for row in matrix]


def _quadratic_form(vector: list[float], matrix: list[list[float]]) -> float:
    mv = _mat_vec(matrix, vector)
    return sum(vector[i] * mv[i] for i in range(len(vector)))


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
        raise ValueError("Нужен хотя бы один фактор риска.")
    if len(correlation_matrix) != n:
        raise ValueError("Размер correlation matrix не совпадает с количеством факторов.")
    validate_correlation_matrix(correlation_matrix)

    covariance = [[0.0 for _ in range(n)] for _ in range(n)]
    for i in range(n):
        if sigma_values[i] < 0:
            raise ValueError("Sigma не может быть отрицательной.")
        for j in range(n):
            covariance[i][j] = (
                correlation_matrix[i][j] * sigma_values[i] * sigma_values[j]
            )
    validate_covariance_matrix(covariance)
    return covariance


def _semi_cholesky(covariance_matrix: list[list[float]], tol: float = 1e-12) -> list[list[float]]:
    n = len(covariance_matrix)
    if n == 0:
        raise ValueError("Матрица ковариации не может быть пустой.")
    for row in covariance_matrix:
        if len(row) != n:
            raise ValueError("Матрица ковариации должна быть квадратной.")

    lower = [[0.0 for _ in range(n)] for _ in range(n)]
    for i in range(n):
        for j in range(i + 1):
            sum_ik_jk = 0.0
            for k in range(j):
                sum_ik_jk += lower[i][k] * lower[j][k]
            value = covariance_matrix[i][j] - sum_ik_jk

            if i == j:
                if value < -tol:
                    raise ValueError(
                        "Матрица ковариации не является PSD (полуопределенной)."
                    )
                lower[i][j] = math.sqrt(max(0.0, value))
            else:
                if abs(lower[j][j]) <= tol:
                    if abs(value) > tol:
                        raise ValueError(
                            "Матрица ковариации не является PSD (проблема в нулевом pivot)."
                        )
                    lower[i][j] = 0.0
                else:
                    lower[i][j] = value / lower[j][j]
    return lower


def sample_multivariate_normal(
    mean_vector: list[float],
    covariance_matrix: list[list[float]],
    simulations: int,
    seed: int,
) -> list[list[float]]:
    if simulations < 2:
        raise ValueError("Количество симуляций должно быть >= 2.")
    n = len(mean_vector)
    if n == 0:
        raise ValueError("Mean vector не может быть пустым.")
    if len(covariance_matrix) != n:
        raise ValueError("Размер covariance matrix не совпадает с размером mean vector.")
    validate_covariance_matrix(covariance_matrix)

    lower = _semi_cholesky(covariance_matrix)
    rng = random.Random(seed)

    scenarios = []
    for _ in range(simulations):
        z = [rng.gauss(0.0, 1.0) for _ in range(n)]
        x = [0.0 for _ in range(n)]
        for i in range(n):
            x_i = mean_vector[i]
            for k in range(i + 1):
                x_i += lower[i][k] * z[k]
            x[i] = x_i
        scenarios.append(x)
    return scenarios


def sample_normal(
    mean_value: float,
    sigma_value: float,
    simulations: int,
    seed: int,
) -> list[float]:
    if simulations < 2:
        raise ValueError("Количество симуляций должно быть >= 2.")
    if sigma_value < 0:
        raise ValueError("Sigma для normal-shock не может быть отрицательной.")
    if sigma_value == 0:
        return [mean_value for _ in range(simulations)]

    rng = random.Random(seed)
    return [rng.gauss(mean_value, sigma_value) for _ in range(simulations)]


def option_var_moment_approximations(
    delta_cash: float,
    gamma_cash: float,
    theta_horizon: float,
    mu_horizon: float,
    sigma_horizon: float,
    z_value: float,
) -> dict[str, float]:
    # Delta-Normal: PnL ~= delta_cash * r + theta.
    mu_dn = delta_cash * mu_horizon + theta_horizon
    sigma_dn = abs(delta_cash) * sigma_horizon
    q_dn = mu_dn - z_value * sigma_dn
    var_dn = max(0.0, -q_dn)

    # Delta-Gamma with moment-matching normal approximation.
    mu_dg = (
        delta_cash * mu_horizon
        + 0.5 * gamma_cash * (mu_horizon ** 2 + sigma_horizon ** 2)
        + theta_horizon
    )
    var_dg = (
        (sigma_horizon ** 2) * ((delta_cash + gamma_cash * mu_horizon) ** 2)
        + 0.5 * (gamma_cash ** 2) * (sigma_horizon ** 4)
    )
    sigma_dg = math.sqrt(max(0.0, var_dg))
    q_dg = mu_dg - z_value * sigma_dg
    var_dg_loss = max(0.0, -q_dg)

    return {
        "mu_dn": mu_dn,
        "sigma_dn": sigma_dn,
        "q_dn": q_dn,
        "var_dn": var_dn,
        "mu_dg": mu_dg,
        "sigma_dg": sigma_dg,
        "q_dg": q_dg,
        "var_dg": var_dg_loss,
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
        raise ValueError("Размеры векторов/матрицы для multifactor Delta-Gamma не совпадают.")
    for row in covariance_horizon:
        if len(row) != n:
            raise ValueError("Covariance matrix должна быть квадратной.")
    validate_covariance_matrix(covariance_horizon)

    gamma_matrix = gamma_cross_matrix or gamma_matrix_from_diagonal(gamma_cash_values)
    _validate_gamma_matrix(gamma_matrix, n)

    mu_dn = theta_horizon
    for i in range(n):
        mu_dn += delta_cash_values[i] * mu_horizon_values[i]

    var_dn = 0.0
    for i in range(n):
        for j in range(n):
            var_dn += (
                delta_cash_values[i]
                * covariance_horizon[i][j]
                * delta_cash_values[j]
            )
    sigma_dn = math.sqrt(max(0.0, var_dn))
    q_dn = mu_dn - z_value * sigma_dn
    var_dn_loss = max(0.0, -q_dn)

    mu_dg = mu_dn
    for i in range(n):
        for j in range(n):
            mu_dg += 0.5 * gamma_matrix[i][j] * (
                covariance_horizon[i][j] + mu_horizon_values[i] * mu_horizon_values[j]
            )

    var_l = var_dn
    sigma_gamma = _mat_mul(covariance_horizon, gamma_matrix)
    gamma_sigma = _mat_mul(gamma_matrix, covariance_horizon)
    gamma_sigma_gamma = _mat_mul(gamma_matrix, sigma_gamma)
    cov_l_q = sum(
        delta_cash_values[i] * sigma_gamma[i][j] * mu_horizon_values[j]
        for i in range(n)
        for j in range(n)
    )
    var_q = 0.5 * _trace_product(gamma_sigma, gamma_sigma)
    var_q += _quadratic_form(mu_horizon_values, gamma_sigma_gamma)

    var_dg = max(0.0, var_l + var_q + 2.0 * cov_l_q)
    sigma_dg = math.sqrt(var_dg)
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
    seed: int,
) -> list[float]:
    if simulations < 2:
        raise ValueError("Количество симуляций должно быть >= 2.")

    if sigma_horizon == 0:
        deterministic_pnl = (
            delta_cash * mu_horizon
            + 0.5 * gamma_cash * (mu_horizon ** 2)
            + theta_horizon
        )
        return [deterministic_pnl for _ in range(simulations)]

    rng = random.Random(seed)
    pnl = []
    for _ in range(simulations):
        shock = rng.gauss(mu_horizon, sigma_horizon)
        pnl_value = (
            delta_cash * shock
            + 0.5 * gamma_cash * (shock ** 2)
            + theta_horizon
        )
        pnl.append(pnl_value)
    return pnl


def simulate_delta_gamma_pnl_multifactor(
    delta_cash_values: list[float],
    gamma_cash_values: list[float],
    theta_horizon: float,
    mean_vector: list[float],
    covariance_matrix: list[list[float]],
    simulations: int,
    seed: int,
    gamma_cross_matrix: list[list[float]] | None = None,
) -> list[float]:
    n = len(delta_cash_values)
    if len(gamma_cash_values) != n or len(mean_vector) != n:
        raise ValueError("Размеры векторов для multifactor Delta-Gamma не совпадают.")
    gamma_matrix = gamma_cross_matrix or gamma_matrix_from_diagonal(gamma_cash_values)
    _validate_gamma_matrix(gamma_matrix, n)

    scenarios = sample_multivariate_normal(
        mean_vector=mean_vector,
        covariance_matrix=covariance_matrix,
        simulations=simulations,
        seed=seed,
    )
    pnl = []
    for scenario in scenarios:
        pnl_value = theta_horizon
        for i in range(n):
            pnl_value += delta_cash_values[i] * scenario[i]
            for j in range(n):
                pnl_value += 0.5 * gamma_matrix[i][j] * scenario[i] * scenario[j]
        pnl.append(pnl_value)
    return pnl


def simulate_full_revaluation_pnl(
    positions: list[dict[str, float | str]],
    horizon_days: int,
    mu_horizon: float,
    sigma_horizon: float,
    simulations: int,
    seed: int,
    vol_mean_horizon: float = 0.0,
    vol_sigma_horizon: float = 0.0,
    rate_mean_horizon: float = 0.0,
    rate_sigma_horizon: float = 0.0,
) -> list[float]:
    return simulate_full_revaluation_pnl_multifactor(
        positions=positions,
        horizon_days=horizon_days,
        underlying_order=["U1"],
        mean_vector=[mu_horizon],
        covariance_matrix=[[sigma_horizon ** 2]],
        simulations=simulations,
        seed=seed,
        vol_mean_horizon=vol_mean_horizon,
        vol_sigma_horizon=vol_sigma_horizon,
        rate_mean_horizon=rate_mean_horizon,
        rate_sigma_horizon=rate_sigma_horizon,
    )


def simulate_full_revaluation_pnl_multifactor(
    positions: list[dict[str, float | str]],
    horizon_days: int,
    underlying_order: list[str],
    mean_vector: list[float],
    covariance_matrix: list[list[float]],
    simulations: int,
    seed: int,
    vol_mean_horizon: float = 0.0,
    vol_sigma_horizon: float = 0.0,
    rate_mean_horizon: float = 0.0,
    rate_sigma_horizon: float = 0.0,
) -> list[float]:
    if horizon_days <= 0:
        raise ValueError("Горизонт должен быть > 0 дней.")
    if not underlying_order:
        raise ValueError("Список underlying не может быть пустым.")
    if len(underlying_order) != len(mean_vector):
        raise ValueError("Размеры underlying_order и mean_vector не совпадают.")

    underlying_index = {name: idx for idx, name in enumerate(underlying_order)}
    scenarios = sample_multivariate_normal(
        mean_vector=mean_vector,
        covariance_matrix=covariance_matrix,
        simulations=simulations,
        seed=seed,
    )
    vol_shocks = sample_normal(
        mean_value=vol_mean_horizon,
        sigma_value=vol_sigma_horizon,
        simulations=simulations,
        seed=seed + 1,
    )
    rate_shocks = sample_normal(
        mean_value=rate_mean_horizon,
        sigma_value=rate_sigma_horizon,
        simulations=simulations,
        seed=seed + 2,
    )

    horizon_years = horizon_days / 365.0
    base_prices = []
    for position in positions:
        base = black_scholes_price_and_greeks(
            option_type=str(position["option_type"]),
            spot=float(position["spot"]),
            strike=float(position["strike"]),
            maturity_years=float(position["maturity_years"]),
            rate=float(position["rate"]),
            volatility=float(position["volatility"]),
            dividend_yield=float(position["dividend_yield"]),
        )["price"]
        base_prices.append(base)

    pnl = []
    for scenario_idx, scenario in enumerate(scenarios):
        total_pnl = 0.0
        vol_shock = vol_shocks[scenario_idx]
        rate_shock = rate_shocks[scenario_idx]
        for idx, position in enumerate(positions):
            option_type = normalize_option_type(str(position["option_type"]))
            spot0 = float(position["spot"])
            strike = float(position["strike"])
            maturity_years = float(position["maturity_years"])
            base_rate = float(position["rate"])
            base_volatility = float(position["volatility"])
            dividend_yield = float(position["dividend_yield"])
            scale = float(position["quantity"]) * float(position["multiplier"])
            underlying_id = str(position.get("underlying_id", "U1"))

            if underlying_id not in underlying_index:
                raise ValueError(
                    f"Underlying '{underlying_id}' из позиции отсутствует в underlying_order."
                )
            shock = scenario[underlying_index[underlying_id]]
            spot_scenario = max(1e-12, spot0 * (1.0 + shock))
            remaining_maturity = maturity_years - horizon_years
            rate_scenario = base_rate + rate_shock
            volatility_scenario = max(1e-8, base_volatility + vol_shock)

            if remaining_maturity > 0:
                scenario_price = black_scholes_price_and_greeks(
                    option_type=option_type,
                    spot=spot_scenario,
                    strike=strike,
                    maturity_years=remaining_maturity,
                    rate=rate_scenario,
                    volatility=volatility_scenario,
                    dividend_yield=dividend_yield,
                )["price"]
            else:
                scenario_price = option_intrinsic_value(
                    option_type=option_type,
                    spot=spot_scenario,
                    strike=strike,
                )

            total_pnl += scale * (scenario_price - base_prices[idx])
        pnl.append(total_pnl)
    return pnl
