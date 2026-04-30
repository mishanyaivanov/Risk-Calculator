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
        one_liner = "По текущей дневной настройке риска позиция выглядит управляемой."
    elif severity == "yellow":
        one_liner = "Позиция ещё выглядит рабочей, но плохой день уже может быть заметным."
    else:
        one_liner = "В один плохой день позиция может дать заметный убыток, поэтому ей нужно уделить внимание."

    if tail_ratio >= 1.35:
        main_message = "Очень плохие дни выглядят заметно хуже базовой оценки VaR, поэтому хвостовой риск здесь важен."
    elif liquidity_addon > 0.1 * max(var_loss, 1.0):
        main_message = "Проблема не только в рыночном риске: принудительный выход из позиции может заметно ухудшить результат."
    else:
        main_message = "Базовая оценка рыночного риска и более консервативные проверки в целом согласуются друг с другом."

    signals = [
        {
            "label": "Дневной риск",
            "severity": severity,
            "value": f"{loss_share_pct:.2f}% от размера позиции",
            "explanation": "Показывает, насколько велика модельная однодневная потеря относительно размера позиции.",
        },
        {
            "label": "Тяжесть хвоста",
            "severity": "red" if tail_ratio >= 1.35 else ("yellow" if tail_ratio >= 1.15 else "green"),
            "value": f"ES / VaR = {tail_ratio:.2f}",
            "explanation": "Expected Shortfall сравнивает средний убыток в очень плохие дни с обычным порогом VaR.",
        },
        {
            "label": "Давление ликвидности",
            "severity": "red" if liquidity_addon > 0.2 * max(var_loss, 1.0) else ("yellow" if liquidity_addon > 0 else "green"),
            "value": _fmt_money(liquidity_addon),
            "explanation": "Это дополнительный убыток, который появляется из-за стрессовой ликвидации по сравнению с базовым VaR.",
        },
        {
            "label": "Сверка моделей",
            "severity": "yellow" if abs(var_loss - hvar_loss) > 0.2 * max(var_loss, 1.0) else "green",
            "value": f"Hist VaR {_fmt_money(hvar_loss)} vs Param VaR {_fmt_money(var_loss)}",
            "explanation": "Большой разрыв между историческим и параметрическим VaR означает, что итог чувствителен к выбранной модели.",
        },
    ]

    actions = []
    if severity == "red":
        actions.append("Уменьшите размер позиции или разбейте сделку, если такой объём риска не был вашей целью.")
        actions.append("Перед тем как считать риск приемлемым, обязательно прогоните стресс-сценарий.")
    elif severity == "yellow":
        actions.append("Держите позицию под контролем и сравните её со стресс-сценариями.")
    else:
        actions.append("Для выбранного горизонта и confidence level это выглядит как разумный базовый уровень риска.")

    if liquidity_addon > 0.0:
        actions.append("Следите за bid-ask spread и предпосылками ликвидации: стоимость выхода здесь тоже важна.")
    if tail_ratio >= 1.25:
        actions.append("Не полагайтесь только на VaR: хвост распределения потерь здесь тяжелее, чем видно из одного порога.")

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
    concentration_asset = (
        asset_names[max_idx]
        if 0 <= max_idx < len(asset_names)
        else "largest asset"
    )

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
        one_liner = "Для текущих входных данных портфель выглядит достаточно сбалансированным."
    elif var_share_pct < 6.0 and max_weight < 0.6:
        severity = "yellow"
        one_liner = "Портфель выглядит рабочим, но концентрация или корреляция уже начинают играть заметную роль."
    else:
        severity = "red"
        one_liner = "Риск портфеля слишком сконцентрирован, чтобы считать его комфортно диверсифицированным."

    if max_weight >= 0.5:
        main_message = f"Главная проблема риска здесь — концентрация в {concentration_asset}."
    elif avg_abs_corr >= 0.65:
        main_message = "Активы двигаются слишком похоже, поэтому диверсификация слабее, чем может казаться по весам."
    elif annual_return < 0 and annual_vol > 0.18:
        main_message = "Портфель берёт на себя заметный риск, но недавняя история не даёт комфортной оценки доходности."
    else:
        main_message = "Структура портфеля выглядит внутренне согласованной: нет одной явной проблемы, которая доминирует над всеми остальными."

    signals = [
        {
            "label": "Portfolio VaR",
            "severity": severity,
            "value": f"{var_share_pct:.2f}% от стоимости портфеля",
            "explanation": "Это модельная однодневная потеря в плохом сценарии относительно полного размера портфеля.",
        },
        {
            "label": "Самый большой вес",
            "severity": "red" if max_weight >= 0.5 else ("yellow" if max_weight >= 0.35 else "green"),
            "value": f"{concentration_asset}: {max_weight * 100:.1f}%",
            "explanation": "Один слишком большой вес может фактически доминировать в портфеле и делать диверсификацию обманчиво красивой.",
        },
        {
            "label": "Качество диверсификации",
            "severity": "red" if avg_abs_corr >= 0.65 else ("yellow" if avg_abs_corr >= 0.45 else "green"),
            "value": f"Avg |corr| = {avg_abs_corr:.2f}",
            "explanation": "Чем выше средняя абсолютная корреляция, тем чаще активы движутся вместе и тем слабее эффект диверсификации.",
        },
        {
            "label": "Баланс риск / доходность",
            "severity": "yellow" if annual_return < 0 else "green",
            "value": f"Доходность {_fmt_pct(annual_return)} vs волатильность {_fmt_pct(annual_vol)}",
            "explanation": "Здесь сравнивается недавняя годовая оценка доходности с годовой волатильностью портфеля.",
        },
    ]

    actions = []
    if max_weight >= 0.5:
        actions.append(f"Снизьте роль {concentration_asset} в портфеле или компенсируйте её другой экспозицией.")
    if avg_abs_corr >= 0.65:
        actions.append("Добавьте активы или хеджи, которые ведут себя по-другому, иначе диверсификация остаётся в основном косметической.")
    if severity == "green":
        actions.append("Используйте этот портфель как хороший базовый сценарий и сравните его со стрессом или хеджем.")
    elif severity == "yellow":
        actions.append("Прогоните стресс-сценарии, чтобы понять, становятся ли слабые места заметно хуже вне нормальных условий.")
    else:
        actions.append("Не останавливайтесь на summary-карточке: текущую структуру стоит ребалансировать или хеджировать до её масштабирования.")

    return {
        "title": "Risk Copilot",
        "severity": severity,
        "one_liner": one_liner,
        "main_message": main_message,
        "signals": signals,
        "actions": actions,
    }
