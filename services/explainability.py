from __future__ import annotations

from typing import Any


def build_single_asset_explanation(
    risk_status: dict[str, Any],
    historical_var_loss: float,
    expected_shortfall_loss: float,
    lvar_loss: float | None = None,
) -> dict[str, Any]:
    severity = str(risk_status.get("severity", "yellow"))
    label = str(risk_status.get("label", "Risk status"))
    loss_share_pct = float(risk_status.get("loss_share_pct", 0.0))
    summary = str(risk_status.get("summary", ""))

    takeaways = [
        f"Parametric VaR is about {loss_share_pct:.2f}% of the current position size.",
        f"Expected Shortfall is {expected_shortfall_loss:.2f}, which represents the average loss across the worst scenarios.",
    ]
    if lvar_loss is not None and lvar_loss > historical_var_loss:
        takeaways.append(
            "Liquidity meaningfully worsens the result: exiting the position under stress is more expensive than the base market-risk estimate."
        )
    else:
        takeaways.append(
            "At the current settings, liquidity does not make the loss materially worse than the base risk estimate."
        )

    next_steps: list[str] = []
    if severity == "red":
        next_steps.extend(
            [
                "Run stress scenarios before increasing this position.",
                "If this level of risk was not intentional, consider reducing size or adding a hedge.",
            ]
        )
    elif severity == "yellow":
        next_steps.extend(
            [
                "Monitor not only VaR, but also position size together with liquidity conditions.",
                "If the instrument is volatile, compare this result with stress scenarios.",
            ]
        )
    else:
        next_steps.extend(
            [
                "At the selected confidence level, the position looks manageable.",
                "For a more conservative view, it is still useful to review stress scenarios.",
            ]
        )

    return {
        "severity": severity,
        "label": label,
        "headline": label,
        "summary": summary,
        "takeaways": takeaways,
        "next_steps": next_steps,
    }


def build_portfolio_explanation(
    portfolio_metrics: dict[str, Any],
    weights: list[float],
    asset_names: list[str],
    correlation_matrix: dict[str, dict[str, float]] | None,
    portfolio_value: float,
) -> dict[str, Any]:
    var_value = float(portfolio_metrics.get("var_value", 0.0))
    annual_volatility = float(portfolio_metrics.get("annual_volatility", 0.0))
    annual_return = float(portfolio_metrics.get("annual_return", 0.0))
    var_share_pct = (var_value / portfolio_value * 100.0) if portfolio_value > 1e-12 else 0.0
    max_weight = max(weights) if weights else 0.0
    max_weight_index = weights.index(max_weight) if weights else -1
    concentration_asset = (
        asset_names[max_weight_index]
        if 0 <= max_weight_index < len(asset_names)
        else "the largest asset"
    )

    avg_abs_correlation = 0.0
    pair_count = 0
    if correlation_matrix:
        names = list(correlation_matrix.keys())
        for i, left in enumerate(names):
            for j, right in enumerate(names):
                if j <= i:
                    continue
                avg_abs_correlation += abs(float(correlation_matrix[left][right]))
                pair_count += 1
    avg_abs_correlation = (avg_abs_correlation / pair_count) if pair_count else 0.0

    if var_share_pct < 3.0 and max_weight < 0.4:
        severity = "green"
        label = "Balanced portfolio"
        summary = "Based on the current inputs, the portfolio looks reasonably diversified."
    elif var_share_pct < 6.0 and max_weight < 0.6:
        severity = "yellow"
        label = "Watch concentration"
        summary = "The portfolio is workable, but one asset or one cluster may already contribute too much risk."
    else:
        severity = "red"
        label = "Risk is concentrated"
        summary = "Portfolio risk is concentrated in a small number of positions and likely needs rebalancing or a hedge."

    takeaways = [
        f"Portfolio VaR is about {var_share_pct:.2f}% of total portfolio value.",
        f"The largest weight is {max_weight * 100:.1f}% in {concentration_asset}.",
        f"Annualized volatility is estimated at {annual_volatility * 100:.2f}%, while annualized expected return is {annual_return * 100:.2f}%.",
    ]
    if pair_count > 0:
        takeaways.append(
            f"Average absolute correlation across assets is {avg_abs_correlation:.2f}, which helps explain diversification quality."
        )

    next_steps: list[str] = []
    if max_weight >= 0.5:
        next_steps.append(f"Reduce concentration in {concentration_asset} or offset it with another exposure.")
    if avg_abs_correlation >= 0.65:
        next_steps.append("Assets move too similarly, so diversification is weaker than the weights may suggest.")
    if severity == "green":
        next_steps.append("Use this as a good baseline portfolio when comparing stress and hedge scenarios.")
    elif severity == "yellow":
        next_steps.append("Run Factor Breakdown or Stress Scenarios to see which part of the structure creates the weak spot.")
    else:
        next_steps.append("The next practical step is a stress test or hedge review: the current structure is too exposed for passive monitoring.")

    return {
        "severity": severity,
        "label": label,
        "headline": label,
        "summary": summary,
        "takeaways": takeaways,
        "next_steps": next_steps,
    }
