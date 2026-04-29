import math

from .option_var import validate_covariance_matrix


def _portfolio_sigma(
    exposures: list[float],
    covariance_matrix: list[list[float]],
) -> float:
    n = len(exposures)
    if n == 0:
        raise ValueError("At least one risk factor is required.")
    if len(covariance_matrix) != n:
        raise ValueError("Covariance matrix size does not match the number of factors.")
    for row in covariance_matrix:
        if len(row) != n:
            raise ValueError("Covariance matrix must be square.")
    validate_covariance_matrix(covariance_matrix)

    variance = 0.0
    for i in range(n):
        for j in range(n):
            variance += exposures[i] * covariance_matrix[i][j] * exposures[j]
    return math.sqrt(max(0.0, variance))


def delta_normal_var_contributions(
    factor_names: list[str],
    delta_cash_values: list[float],
    mu_horizon_values: list[float],
    covariance_horizon: list[list[float]],
    z_value: float,
) -> dict[str, float | list[dict[str, float | str]]]:
    n = len(factor_names)
    if n == 0:
        raise ValueError("At least one risk factor is required.")
    if len(delta_cash_values) != n or len(mu_horizon_values) != n:
        raise ValueError("factor_names, delta_cash_values, and mu_horizon_values must have matching lengths.")

    sigma_portfolio = _portfolio_sigma(delta_cash_values, covariance_horizon)
    mu_portfolio = sum(
        delta_cash_values[i] * mu_horizon_values[i] for i in range(n)
    )
    raw_var_loss = z_value * sigma_portfolio - mu_portfolio
    var_loss = max(0.0, raw_var_loss)

    sigma_safe = max(sigma_portfolio, 1e-12)
    sigma_times_exposure: list[float] = []
    for i in range(n):
        value = 0.0
        for j in range(n):
            value += covariance_horizon[i][j] * delta_cash_values[j]
        sigma_times_exposure.append(value)

    rows: list[dict[str, float | str]] = []
    total_component = 0.0
    for i in range(n):
        if raw_var_loss <= 0.0:
            marginal = 0.0
        else:
            marginal = z_value * (sigma_times_exposure[i] / sigma_safe) - mu_horizon_values[i]
        component = delta_cash_values[i] * marginal
        total_component += component
        rows.append(
            {
                "factor": factor_names[i],
                "delta_cash": delta_cash_values[i],
                "mu_horizon": mu_horizon_values[i],
                "marginal_var": marginal,
                "component_var": component,
                "component_share_pct": 0.0,
            }
        )

    denom = total_component if abs(total_component) > 1e-12 else 1.0
    for row in rows:
        row["component_share_pct"] = float(row["component_var"]) / denom * 100.0

    return {
        "portfolio_mu": mu_portfolio,
        "portfolio_sigma": sigma_portfolio,
        "portfolio_var_raw": raw_var_loss,
        "portfolio_var": var_loss,
        "sum_component_var": total_component,
        "rows": rows,
    }
