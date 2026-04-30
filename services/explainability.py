from __future__ import annotations

from typing import Any


def build_single_asset_explanation(
    risk_status: dict[str, Any],
    historical_var_loss: float,
    expected_shortfall_loss: float,
    lvar_loss: float | None = None,
) -> dict[str, Any]:
    severity = str(risk_status.get("severity", "yellow"))
    label = str(risk_status.get("label", "Статус риска"))
    loss_share_pct = float(risk_status.get("loss_share_pct", 0.0))
    summary = str(risk_status.get("summary", ""))

    takeaways = [
        f"Параметрический VaR составляет около {loss_share_pct:.2f}% от текущего размера позиции.",
        f"Expected Shortfall равен {expected_shortfall_loss:.2f}: это средний убыток в самых плохих сценариях.",
    ]
    if lvar_loss is not None and lvar_loss > historical_var_loss:
        takeaways.append(
            "Ликвидность заметно ухудшает результат: выход из позиции в стрессовых условиях дороже базовой оценки риска."
        )
    else:
        takeaways.append(
            "В текущей настройке ликвидность не делает убыток существенно хуже базовой оценки риска."
        )

    next_steps = []
    if severity == "red":
        next_steps.extend(
            [
                "Перед увеличением позиции проверьте стресс-сценарии.",
                "Если такой риск не был вашей целью, подумайте о снижении объёма или о хедже.",
            ]
        )
    elif severity == "yellow":
        next_steps.extend(
            [
                "Следите не только за VaR, но и за размером позиции вместе с ликвидностью.",
                "Если инструмент волатильный, сравните результат со стресс-сценариями.",
            ]
        )
    else:
        next_steps.extend(
            [
                "При выбранном confidence level позиция выглядит управляемой.",
                "Для более консервативной оценки всё равно полезно посмотреть стресс-сценарии.",
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
    concentration_asset = asset_names[max_weight_index] if max_weight_index >= 0 and max_weight_index < len(asset_names) else "the largest asset"

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
        label = "Сбалансированный портфель"
        summary = "По текущим входным данным портфель выглядит достаточно диверсифицированным."
    elif var_share_pct < 6.0 and max_weight < 0.6:
        severity = "yellow"
        label = "Следите за концентрацией"
        summary = "Портфель рабочий, но один актив или один кластер уже может давать слишком большой вклад в риск."
    else:
        severity = "red"
        label = "Риск сконцентрирован"
        summary = "Риск портфеля заметно сосредоточен в отдельных позициях и требует ребалансировки или хеджа."

    takeaways = [
        f"Portfolio VaR составляет около {var_share_pct:.2f}% от стоимости портфеля.",
        f"Самый большой вес — {max_weight * 100:.1f}% в {concentration_asset}.",
        f"Годовая волатильность оценивается в {annual_volatility * 100:.2f}%, а ожидаемая годовая доходность — в {annual_return * 100:.2f}%.",
    ]
    if pair_count > 0:
        takeaways.append(
            f"Средняя абсолютная корреляция между активами равна {avg_abs_correlation:.2f}. Это помогает понять качество диверсификации."
        )

    next_steps = []
    if max_weight >= 0.5:
        next_steps.append(f"Снизьте концентрацию в {concentration_asset} или компенсируйте её другой экспозицией.")
    if avg_abs_correlation >= 0.65:
        next_steps.append("Активы двигаются слишком похоже, поэтому диверсификация слабее, чем кажется по весам.")
    if severity == "green":
        next_steps.append("Это хороший базовый портфель, с которым можно сравнивать стресс- и hedge-сценарии.")
    elif severity == "yellow":
        next_steps.append("Запустите Factor Breakdown или Stress Scenarios, чтобы увидеть, что именно создаёт слабые места.")
    else:
        next_steps.append("Следующий логичный шаг — стресс-тест или анализ хеджа: текущая структура слишком уязвима для пассивного наблюдения.")

    return {
        "severity": severity,
        "label": label,
        "headline": label,
        "summary": summary,
        "takeaways": next_steps[:0] + takeaways,
        "next_steps": next_steps,
    }
