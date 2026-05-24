from __future__ import annotations

from typing import Any

import numpy as np

from services.portfolio_manager import calculate_portfolio_var


def _scale_single_asset_metrics(base_value: float, factor: float) -> float:
    return max(0.0, base_value * max(0.0, factor))


def _severity_from_share(share_pct: float) -> str:
    if share_pct < 2.0:
        return "green"
    if share_pct < 5.0:
        return "yellow"
    return "red"


def build_single_asset_hedge_constructor(
    position_value: float,
    position_size: float,
    last_price: float,
    parametric_var_loss: float,
    historical_var_loss: float,
    expected_shortfall_loss: float,
    stressed_lvar_loss: float | None,
) -> dict[str, Any]:
    stressed_lvar_loss = float(stressed_lvar_loss or parametric_var_loss)
    base_share_pct = (parametric_var_loss / abs(position_value) * 100.0) if abs(position_value) > 1e-12 else 0.0

    scenarios: list[dict[str, Any]] = []
    scenario_defs = [
        {
            "id": "trim_25",
            "title": "Trim the position by 25%",
            "type": "size_reduction",
            "factor": 0.75,
            "description": "A smaller position reduces market risk almost linearly and remains the simplest way to bring exposure down quickly.",
            "action": "Reduce roughly one quarter of the current position.",
        },
        {
            "id": "trim_50",
            "title": "Trim the position by 50%",
            "type": "size_reduction",
            "factor": 0.50,
            "description": "A deeper reduction gives a stronger risk effect without adding a new instrument.",
            "action": "Cut the current exposure in half.",
        },
        {
            "id": "futures_50",
            "title": "Add a 50% linear hedge",
            "type": "linear_hedge",
            "factor": 0.50,
            "description": "This approximates a short futures or SPFI hedge covering half of the spot exposure.",
            "action": "Open a short hedge with notional close to 50% of the spot position.",
        },
        {
            "id": "futures_75",
            "title": "Add a 75% linear hedge",
            "type": "linear_hedge",
            "factor": 0.25,
            "description": "A stronger hedge cuts daily VaR more aggressively, but leaves less upside and still does not remove basis risk completely.",
            "action": "Open a short hedge with notional close to 75% of the spot position.",
        },
    ]

    for item in scenario_defs:
        factor = float(item["factor"])
        new_position_size = position_size * factor if item["type"] == "size_reduction" else position_size
        residual_notional = abs(position_value) * factor
        var_after = _scale_single_asset_metrics(parametric_var_loss, factor)
        hvar_after = _scale_single_asset_metrics(historical_var_loss, factor)
        es_after = _scale_single_asset_metrics(expected_shortfall_loss, factor)
        lvar_after = _scale_single_asset_metrics(stressed_lvar_loss, factor)
        share_pct = (var_after / abs(position_value) * 100.0) if abs(position_value) > 1e-12 else 0.0
        improvement_pct = ((parametric_var_loss - var_after) / parametric_var_loss * 100.0) if parametric_var_loss > 1e-12 else 0.0

        scenarios.append(
            {
                "id": item["id"],
                "title": item["title"],
                "type": item["type"],
                "description": item["description"],
                "action": item["action"],
                "severity": _severity_from_share(share_pct),
                "before": {
                    "var_loss": parametric_var_loss,
                    "es_loss": expected_shortfall_loss,
                    "lvar_stressed": stressed_lvar_loss,
                    "loss_share_pct": base_share_pct,
                },
                "after": {
                    "var_loss": var_after,
                    "historical_var_loss": hvar_after,
                    "es_loss": es_after,
                    "lvar_stressed": lvar_after,
                    "loss_share_pct": share_pct,
                    "residual_notional": residual_notional,
                    "new_position_size": new_position_size,
                    "improvement_pct": improvement_pct,
                },
                "notes": [
                    "This is a first-order estimate: market risk scales with the remaining unhedged exposure.",
                    "A real futures or SPFI hedge can still leave basis risk, margin requirements, and execution costs outside this quick estimate.",
                ],
                "quick_action": (
                    {
                        "kind": "apply_forward_hedge",
                        "label": "Open in Futures & SPFI",
                        "payload": {
                            "instrument_type": "futures",
                            "spot": last_price,
                            "entry_price": last_price,
                            "maturity_years": 0.25,
                            "rate": 0.05,
                            "income_yield": 0.0,
                            "quantity": position_size * (1.0 - factor),
                            "multiplier": 1.0,
                            "scenario_spot": last_price * 0.95,
                            "hedge_ratio": 1.0 - factor,
                        },
                    }
                    if item["type"] == "linear_hedge"
                    else None
                ),
            }
        )

    return {
        "title": "Hedge Constructor",
        "summary": "Try a few simple hedge scenarios and immediately compare how much they reduce one-day downside before moving to a more complex structure.",
        "spot_price": last_price,
        "position_size": position_size,
        "position_value": position_value,
        "option_bridge": {
            "kind": "apply_option_hedge",
            "label": "Explore a protective put",
            "payload": {
                "option_type": "put",
                "spot": last_price,
                "strike": round(last_price * 0.90, 4),
                "maturity_years": 0.25,
                "rate": 0.05,
                "volatility": 0.25,
                "dividend_yield": 0.0,
                "quantity": position_size,
                "multiplier": 1.0,
            },
        },
        "scenarios": scenarios,
    }


def _redistribute_trim(weights: np.ndarray, largest_index: int, trim_amount: float) -> np.ndarray:
    adjusted = weights.astype(float).copy()
    if adjusted.size == 0:
        return adjusted

    removable = min(trim_amount, float(adjusted[largest_index]))
    adjusted[largest_index] -= removable
    recipients = np.array([idx != largest_index for idx in range(len(adjusted))], dtype=bool)
    if np.any(recipients):
        recipient_sum = float(np.sum(adjusted[recipients]))
        if recipient_sum <= 1e-12:
            adjusted[recipients] += removable / np.sum(recipients)
        else:
            adjusted[recipients] += adjusted[recipients] / recipient_sum * removable

    total = float(np.sum(adjusted))
    if total > 1e-12:
        adjusted /= total
    return adjusted


def _equal_weight_portfolio(size: int) -> np.ndarray:
    if size <= 0:
        return np.array([], dtype=float)
    return np.full(size, 1.0 / size, dtype=float)


def build_portfolio_hedge_constructor(
    returns_matrix: np.ndarray,
    weights: list[float],
    asset_names: list[str],
    confidence: float,
    portfolio_value: float,
) -> dict[str, Any]:
    weights_array = np.array(weights, dtype=float)
    if weights_array.size == 0:
        return {
            "title": "Hedge Constructor",
            "summary": "No ready-made hedge ideas are available for this portfolio yet.",
            "scenarios": [],
        }

    base_metrics = calculate_portfolio_var(
        returns=returns_matrix,
        weights=weights_array,
        confidence=confidence,
        portfolio_value=portfolio_value,
    )
    largest_index = int(np.argmax(weights_array))
    largest_name = asset_names[largest_index] if largest_index < len(asset_names) else "largest asset"
    base_var = float(base_metrics["var_value"])

    scenario_defs = [
        {
            "id": "equal_weight",
            "title": "Move closer to equal weights",
            "description": "This scenario shows a cleaner diversification baseline in which each asset carries an equal share of the portfolio.",
            "action": "Rebalance the portfolio toward equal weights.",
            "weights": _equal_weight_portfolio(len(weights_array)),
        },
        {
            "id": "trim_largest_15pp",
            "title": "Cut the largest position by 15 pp",
            "description": "A partial rebalance is often easier to execute than redesigning the whole portfolio.",
            "action": f"Reduce {largest_name} by 15 percentage points and redistribute the weight across the remaining assets.",
            "weights": _redistribute_trim(weights_array, largest_index, 0.15),
        },
        {
            "id": "market_overlay_20",
            "title": "Add a 20% protective overlay",
            "description": "This approximates a partial index or futures overlay that lowers the aggregate risky exposure of the portfolio.",
            "action": "Add a short overlay equal to roughly 20% of total portfolio notional.",
            "scale_factor": 0.80,
        },
    ]

    scenarios: list[dict[str, Any]] = []
    for item in scenario_defs:
        if "weights" in item:
            candidate_weights = np.array(item["weights"], dtype=float)
            metrics = calculate_portfolio_var(
                returns=returns_matrix,
                weights=candidate_weights,
                confidence=confidence,
                portfolio_value=portfolio_value,
            )
            weights_preview = {
                asset_names[idx]: round(float(candidate_weights[idx]) * 100.0, 2)
                for idx in range(min(len(asset_names), len(candidate_weights)))
            }
        else:
            scale_factor = float(item["scale_factor"])
            metrics = {
                **base_metrics,
                "var_value": float(base_metrics["var_value"]) * scale_factor,
                "annual_volatility": float(base_metrics["annual_volatility"]) * scale_factor,
                "annual_return": float(base_metrics["annual_return"]),
            }
            weights_preview = {
                "Net market exposure": round(scale_factor * 100.0, 2),
                "Overlay hedge": round((1.0 - scale_factor) * 100.0, 2),
            }

        var_after = float(metrics["var_value"])
        improvement_pct = ((base_var - var_after) / base_var * 100.0) if base_var > 1e-12 else 0.0
        share_pct = (var_after / portfolio_value * 100.0) if portfolio_value > 1e-12 else 0.0

        scenarios.append(
            {
                "id": item["id"],
                "title": item["title"],
                "description": item["description"],
                "action": item["action"],
                "severity": _severity_from_share(share_pct),
                "before": {
                    "var_value": base_var,
                    "annual_volatility": float(base_metrics["annual_volatility"]),
                    "loss_share_pct": (base_var / portfolio_value * 100.0) if portfolio_value > 1e-12 else 0.0,
                },
                "after": {
                    "var_value": var_after,
                    "annual_volatility": float(metrics["annual_volatility"]),
                    "annual_return": float(metrics["annual_return"]),
                    "loss_share_pct": share_pct,
                    "improvement_pct": improvement_pct,
                    "weights_preview": weights_preview,
                },
                "notes": [
                    "This is a quick decision-support scenario, not an optimizer that accounts for all transaction costs.",
                    "The goal is to show the direction of risk change after rebalancing or hedging before deeper analysis.",
                ],
                "quick_action": (
                    {
                        "kind": "apply_portfolio_weights",
                        "label": "Apply these weights",
                        "payload": {
                            "weights": candidate_weights.tolist(),
                        },
                    }
                    if "weights" in item
                    else None
                ),
            }
        )

    return {
        "title": "Hedge Constructor",
        "summary": "These scenarios show simple ways to reduce concentration or total market exposure without rebuilding the full workflow.",
        "largest_asset": largest_name,
        "scenarios": scenarios,
    }
