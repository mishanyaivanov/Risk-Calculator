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
            "title": "Сократить позицию на 25%",
            "type": "size_reduction",
            "factor": 0.75,
            "description": "Меньшая позиция почти линейно снижает рыночный риск и остаётся самым простым способом быстро уменьшить нагрузку.",
            "action": "Сократите примерно четверть текущей позиции.",
        },
        {
            "id": "trim_50",
            "title": "Сократить позицию на 50%",
            "type": "size_reduction",
            "factor": 0.50,
            "description": "Более глубокое сокращение даёт сильный эффект по риску без добавления нового инструмента.",
            "action": "Сократите текущую экспозицию вдвое.",
        },
        {
            "id": "futures_50",
            "title": "Добавить линейный хедж на 50%",
            "type": "linear_hedge",
            "factor": 0.50,
            "description": "Это приближённо моделирует короткий фьючерсный или SPFI-хедж на половину экспозиции.",
            "action": "Откройте короткий хедж с номиналом около 50% от спотовой позиции.",
        },
        {
            "id": "futures_75",
            "title": "Добавить линейный хедж на 75%",
            "type": "linear_hedge",
            "factor": 0.25,
            "description": "Более сильный хедж заметно снижает дневной VaR, но при этом оставляет меньше upside и всё ещё не убирает basis risk полностью.",
            "action": "Откройте короткий хедж с номиналом около 75% от спотовой позиции.",
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
                    "Это оценка первого порядка: рыночный риск масштабируется вместе с оставшейся незахеджированной экспозицией.",
                    "Реальный фьючерсный или SPFI-хедж всё равно может оставлять basis risk, требования по марже и издержки исполнения за пределами этой быстрой оценки.",
                ],
                "quick_action": (
                    {
                        "kind": "apply_forward_hedge",
                        "label": "Открыть в Futures & SPFI",
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
        "summary": "Попробуйте несколько простых hedge-сценариев и сразу посмотрите, насколько они уменьшают однодневный downside до перехода к более сложной конструкции.",
        "spot_price": last_price,
        "position_size": position_size,
        "position_value": position_value,
        "option_bridge": {
            "kind": "apply_option_hedge",
            "label": "Изучить protective put",
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


def _rebalance_with_cap(weights: np.ndarray, max_weight: float) -> np.ndarray:
    adjusted = weights.astype(float).copy()
    if adjusted.size == 0:
        return adjusted

    while True:
        above = adjusted > max_weight
        if not np.any(above):
            break

        excess = float(np.sum(adjusted[above] - max_weight))
        adjusted[above] = max_weight
        recipients = ~above
        if not np.any(recipients):
            break

        recipient_sum = float(np.sum(adjusted[recipients]))
        if recipient_sum <= 1e-12:
            adjusted[recipients] += excess / np.sum(recipients)
        else:
            adjusted[recipients] += adjusted[recipients] / recipient_sum * excess

    adjusted = np.clip(adjusted, 0.0, None)
    total = float(np.sum(adjusted))
    if total > 1e-12:
        adjusted /= total
    return adjusted


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
            "summary": "Для этого портфеля пока нет готовых hedge-идей.",
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
            "title": "Перейти ближе к равным весам",
            "description": "Этот сценарий показывает более чистую базу диверсификации, где каждый актив несёт одинаковую долю портфеля.",
            "action": "Ребалансируйте портфель в сторону равных весов.",
            "weights": _equal_weight_portfolio(len(weights_array)),
        },
        {
            "id": "trim_largest_15pp",
            "title": "Снизить крупнейшую позицию на 15 п.п.",
            "description": "Частичный ребаланс обычно легче исполнить, чем полностью переделывать портфель.",
            "action": f"Снизьте {largest_name} на 15 процентных пунктов и перераспределите вес по остальным активам.",
            "weights": _redistribute_trim(weights_array, largest_index, 0.15),
        },
        {
            "id": "market_overlay_20",
            "title": "Добавить защитный overlay на 20%",
            "description": "Это приближённо моделирует частичный индексный или фьючерсный overlay, который снижает суммарную рискованную экспозицию портфеля.",
            "action": "Добавьте короткий overlay примерно на 20% от общего номинала портфеля.",
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
                    "Это быстрый сценарий поддержки решения, а не оптимизатор с учётом всех транзакционных издержек.",
                    "Цель — показать направление изменения риска после ребалансировки или хеджа до более глубокого анализа.",
                ],
                "quick_action": (
                    {
                        "kind": "apply_portfolio_weights",
                        "label": "Применить эти веса",
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
        "summary": "Эти сценарии показывают простые способы снизить концентрацию или суммарную рыночную экспозицию без полной перестройки workflow.",
        "largest_asset": largest_name,
        "scenarios": scenarios,
    }
