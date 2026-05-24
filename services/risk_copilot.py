from __future__ import annotations

from typing import Any


def _fmt_money(value: float) -> str:
    return f"{value:,.2f}".replace(",", " ")


def _fmt_pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def build_single_asset_copilot(
    risk_status: dict[str, Any],
    historical_var: dict[str, Any],
    expected_shortfall: dict[str, Any],
    parametric_var: dict[str, Any],
    lvar: dict[str, Any],
    confidence: float,
) -> dict[str, Any]:
    severity = str(risk_status.get("severity", "yellow"))
    loss_share_pct = float(risk_status.get("loss_share_pct", 0.0))
    var_loss = float(parametric_var.get("var_loss", 0.0))
    es_loss = float(expected_shortfall.get("es_loss", 0.0))
    hvar_loss = float(historical_var.get("var_loss", 0.0))
    stressed_lvar = float(lvar.get("lvar_stressed", var_loss))
    liquidity_addon = max(0.0, stressed_lvar - var_loss)
    tail_ratio = (es_loss / var_loss) if var_loss > 1e-12 else 1.0

    if severity == "green":
        one_liner = "At the current daily settings, the position looks manageable."
    elif severity == "yellow":
        one_liner = "The position still looks workable, but a bad day could already be noticeable."
    else:
        one_liner = "One bad day could create a meaningful loss, so this position needs attention."

    if tail_ratio >= 1.35:
        main_message = "Very bad days look materially worse than the base VaR estimate, so tail risk matters here."
    elif liquidity_addon > 0.1 * max(var_loss, 1.0):
        main_message = "The issue is not only market risk: forced liquidation could materially worsen the outcome."
    else:
        main_message = "The base market-risk estimate and the more conservative checks are broadly consistent with each other."

    signals = [
        {
            "label": "Daily risk",
            "severity": severity,
            "value": f"{loss_share_pct:.2f}% of position size",
            "explanation": "This shows the modeled one-day loss relative to the size of the position.",
        },
        {
            "label": "Tail severity",
            "severity": "red" if tail_ratio >= 1.35 else ("yellow" if tail_ratio >= 1.15 else "green"),
            "value": f"ES / VaR = {tail_ratio:.2f}",
            "explanation": "Expected Shortfall compares the average loss in very bad days with the usual VaR threshold.",
        },
        {
            "label": "Liquidity pressure",
            "severity": "red" if liquidity_addon > 0.2 * max(var_loss, 1.0) else ("yellow" if liquidity_addon > 0 else "green"),
            "value": _fmt_money(liquidity_addon),
            "explanation": "This is the extra loss introduced by stressed liquidation compared with base VaR.",
        },
        {
            "label": "Model cross-check",
            "severity": "yellow" if abs(var_loss - hvar_loss) > 0.2 * max(var_loss, 1.0) else "green",
            "value": f"Hist VaR {_fmt_money(hvar_loss)} vs Param VaR {_fmt_money(var_loss)}",
            "explanation": "A large gap between historical and parametric VaR means the result depends strongly on model choice.",
        },
    ]

    actions: list[str] = []
    if severity == "red":
        actions.append("Reduce the position size or split execution if this amount of risk was not intentional.")
        actions.append("Run a stress scenario before treating this position as acceptable.")
    elif severity == "yellow":
        actions.append("Keep the position under review and compare it with stress scenarios.")
    else:
        actions.append(f"For the selected horizon and {confidence:.1%} confidence level, this looks like a reasonable baseline risk level.")

    if liquidity_addon > 0.0:
        actions.append("Monitor bid-ask spread and liquidation assumptions, because exit cost matters here as well.")
    if tail_ratio >= 1.25:
        actions.append("Do not rely on VaR alone: the loss tail is heavier than a single threshold may suggest.")

    return {
        "title": "Risk Copilot",
        "severity": severity,
        "one_liner": one_liner,
        "main_message": main_message,
        "signals": signals,
        "actions": actions,
    }


def build_portfolio_copilot(
    portfolio_metrics: dict[str, Any],
    weights: list[float],
    asset_names: list[str],
    correlation_matrix: dict[str, dict[str, float]] | None,
    portfolio_value: float,
) -> dict[str, Any]:
    var_value = float(portfolio_metrics.get("var_value", 0.0))
    annual_return = float(portfolio_metrics.get("annual_return", 0.0))
    annual_vol = float(portfolio_metrics.get("annual_volatility", 0.0))
    var_share_pct = (var_value / portfolio_value * 100.0) if portfolio_value > 1e-12 else 0.0

    max_weight = max(weights) if weights else 0.0
    max_idx = weights.index(max_weight) if weights else -1
    concentration_asset = asset_names[max_idx] if 0 <= max_idx < len(asset_names) else "largest asset"

    avg_abs_corr = 0.0
    pair_count = 0
    if correlation_matrix:
        names = list(correlation_matrix.keys())
        for i, left in enumerate(names):
            for j, right in enumerate(names):
                if j <= i:
                    continue
                avg_abs_corr += abs(float(correlation_matrix[left][right]))
                pair_count += 1
    avg_abs_corr = (avg_abs_corr / pair_count) if pair_count else 0.0

    if var_share_pct < 3.0 and max_weight < 0.4 and avg_abs_corr < 0.45:
        severity = "green"
        one_liner = "For the current inputs, the portfolio looks reasonably balanced."
    elif var_share_pct < 6.0 and max_weight < 0.6:
        severity = "yellow"
        one_liner = "The portfolio looks workable, but concentration or correlation is already becoming visible."
    else:
        severity = "red"
        one_liner = "Portfolio risk is too concentrated to be treated as comfortably diversified."

    if max_weight >= 0.5:
        main_message = f"The main problem here is concentration in {concentration_asset}."
    elif avg_abs_corr >= 0.65:
        main_message = "Assets move too similarly, so diversification is weaker than the weights may suggest."
    elif annual_return < 0 and annual_vol > 0.18:
        main_message = "The portfolio is taking noticeable risk, but recent history does not support a comfortable return outlook."
    else:
        main_message = "The portfolio structure looks internally consistent, with no single issue dominating all the others."

    signals = [
        {
            "label": "Portfolio VaR",
            "severity": severity,
            "value": f"{var_share_pct:.2f}% of portfolio value",
            "explanation": "This is the modeled one-day loss in a bad scenario relative to total portfolio size.",
        },
        {
            "label": "Largest weight",
            "severity": "red" if max_weight >= 0.5 else ("yellow" if max_weight >= 0.35 else "green"),
            "value": f"{concentration_asset}: {max_weight * 100:.1f}%",
            "explanation": "One oversized position can dominate the portfolio and make diversification look better than it really is.",
        },
        {
            "label": "Diversification quality",
            "severity": "red" if avg_abs_corr >= 0.65 else ("yellow" if avg_abs_corr >= 0.45 else "green"),
            "value": f"Avg |corr| = {avg_abs_corr:.2f}",
            "explanation": "The higher the average absolute correlation, the more often assets move together and the weaker diversification becomes.",
        },
        {
            "label": "Risk / return balance",
            "severity": "yellow" if annual_return < 0 else "green",
            "value": f"Return {_fmt_pct(annual_return)} vs volatility {_fmt_pct(annual_vol)}",
            "explanation": "This compares the recent annualized return estimate with annualized portfolio volatility.",
        },
    ]

    actions: list[str] = []
    if max_weight >= 0.5:
        actions.append(f"Reduce the role of {concentration_asset} in the portfolio or offset it with another exposure.")
    if avg_abs_corr >= 0.65:
        actions.append("Add assets or hedges that behave differently, otherwise diversification remains mostly cosmetic.")
    if severity == "green":
        actions.append("Use this portfolio as a good baseline case when comparing stress or hedge scenarios.")
    elif severity == "yellow":
        actions.append("Run stress scenarios to see whether the weak spot becomes materially worse outside normal conditions.")
    else:
        actions.append("Do not stop at the summary card: the current structure should be rebalanced or hedged before scaling it further.")

    return {
        "title": "Risk Copilot",
        "severity": severity,
        "one_liner": one_liner,
        "main_message": main_message,
        "signals": signals,
        "actions": actions,
    }
