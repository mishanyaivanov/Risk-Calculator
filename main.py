import math
from statistics import mean, stdev

# One-tailed z-values for left-tail VaR at supported confidence levels.
Z_BY_CONFIDENCE = {
    0.95: 1.645,
    0.99: 2.326,
}


def parse_number_list(raw: str) -> list[float]:
    items = [x.strip() for x in raw.replace(";", ",").split(",") if x.strip()]
    if len(items) < 2:
        raise ValueError("Нужно минимум 2 числа.")
    try:
        return [float(x) for x in items]
    except ValueError as exc:
        raise ValueError("Список должен содержать только числа.") from exc


def normalize_confidence(raw: str) -> float:
    text = raw.strip().replace(",", ".")
    try:
        value = float(text)
    except ValueError as exc:
        raise ValueError("Уровень доверия должен быть числом (например, 95 или 0.95).") from exc

    if value > 1:
        value = value / 100.0

    # Protect against floating-point representation noise before dictionary lookup.
    value = round(value, 4)

    if value not in Z_BY_CONFIDENCE:
        supported = ", ".join(f"{int(c * 100)}%" for c in sorted(Z_BY_CONFIDENCE))
        raise ValueError(f"Неподдерживаемый уровень доверия: {value:.4f}. Доступно: {supported}.")
    return value


def z_value_for_confidence(confidence: float) -> float:
    if confidence not in Z_BY_CONFIDENCE:
        raise ValueError("Для этого confidence нет one-tailed z-значения в настройках калькулятора.")
    return Z_BY_CONFIDENCE[confidence]


def pnl_from_prices(prices: list[float], position_size: float = 1.0) -> list[float]:
    if len(prices) < 2:
        raise ValueError("Для расчета P&L из цен нужно минимум 2 цены.")
    return [position_size * (prices[i] - prices[i - 1]) for i in range(1, len(prices))]


def pnl_from_returns(returns: list[float], position_value: float, returns_in_percent: bool) -> list[float]:
    scale = 0.01 if returns_in_percent else 1.0
    return [position_value * (r * scale) for r in returns]


def aggregate_pnl_series(series_list: list[list[float]]) -> list[float]:
    if not series_list:
        raise ValueError("Нужен хотя бы один ряд P&L для агрегации.")
    length = len(series_list[0])
    if length == 0:
        raise ValueError("Ряды P&L не могут быть пустыми.")
    for idx, series in enumerate(series_list, start=1):
        if len(series) != length:
            raise ValueError(
                f"Все ряды P&L должны быть одной длины. Ряд 1: {length}, ряд {idx}: {len(series)}."
            )
    return [sum(day_values) for day_values in zip(*series_list)]


def historical_var_discrete(pnl: list[float], confidence: float) -> tuple[float, float, int]:
    if len(pnl) < 2:
        raise ValueError("Для Historical VaR нужно минимум 2 наблюдения P&L.")

    alpha = 1.0 - confidence
    sorted_pnl = sorted(pnl)  # Worst losses are first (most negative values).
    n = len(sorted_pnl)
    k = max(1, math.ceil(n * alpha))  # ceil(n*alpha)-th worst P&L, no interpolation.
    var_pnl = sorted_pnl[k - 1]

    # Sign convention: P&L losses are negative, while VaR is reported as positive loss magnitude.
    var_loss = max(0.0, -var_pnl)
    return var_loss, var_pnl, k


def expected_shortfall_discrete(pnl: list[float], confidence: float) -> tuple[float, float, int]:
    if len(pnl) < 2:
        raise ValueError("Для Expected Shortfall нужно минимум 2 наблюдения P&L.")

    alpha = 1.0 - confidence
    sorted_pnl = sorted(pnl)
    n = len(sorted_pnl)
    tail_count = max(1, math.ceil(n * alpha))
    tail = sorted_pnl[:tail_count]
    es_pnl = sum(tail) / tail_count

    # ES is also reported as positive loss magnitude.
    es_loss = max(0.0, -es_pnl)
    return es_loss, es_pnl, tail_count


def parametric_var(pnl: list[float], confidence: float) -> tuple[float, float, float, float]:
    if len(pnl) < 2:
        raise ValueError("Для параметрического VaR нужно минимум 2 наблюдения P&L.")

    mu = mean(pnl)
    sigma = stdev(pnl)
    z = z_value_for_confidence(confidence)

    # Left-tail one-tailed normal quantile for P&L.
    q_alpha_pnl = mu - z * sigma
    var_loss = max(0.0, -q_alpha_pnl)
    return var_loss, q_alpha_pnl, mu, sigma


def normal_liquidation_cost(mid_market_value: float, spread_percent: float) -> float:
    return 0.5 * abs(mid_market_value) * (spread_percent / 100.0)


def stressed_liquidation_cost(
    mid_market_value: float,
    spread_percent: float,
    confidence: float,
    sigma_spread_percent: float,
) -> float:
    z = z_value_for_confidence(confidence)
    s = spread_percent / 100.0
    sigma_s = sigma_spread_percent / 100.0
    return 0.5 * abs(mid_market_value) * (s + z * sigma_s)


def linear_unwind_adjustment_factor(days: int) -> float:
    if days <= 0:
        raise ValueError("Период ликвидации T должен быть > 0.")
    return math.sqrt(((1 + days) * (1 + 2 * days)) / (6 * days))


def linear_unwind_adjusted_var(base_var: float, days: int) -> float:
    # Excel-note formula for uniform (linear) liquidation over T days.
    factor = linear_unwind_adjustment_factor(days)
    return base_var / factor


def ask_confidence() -> float:
    return normalize_confidence(input("Уровень доверия (95 / 99 или 0.95 / 0.99): "))


def ask_single_series_pnl(instrument_label: str = "") -> list[float]:
    prefix = f"[{instrument_label}] " if instrument_label else ""
    print(f"{prefix}Источник данных:")
    print("1. Ряд цен -> денежный P&L через разности (с учетом множителя позиции)")
    print("2. Ряд денежного P&L (уже в деньгах по инструменту)")
    print("3. Ряд доходностей -> денежный P&L через размер позиции")
    mode = input(f"{prefix}Выберите режим (1-3): ").strip()
    raw = input(f"{prefix}Вставьте числа через запятую: ").strip()
    values = parse_number_list(raw)

    if mode == "1":
        position_size_raw = input(
            f"{prefix}Множитель позиции для разностей цен (по умолчанию 1): "
        ).strip()
        position_size = float(position_size_raw) if position_size_raw else 1.0
        return pnl_from_prices(values, position_size=position_size)

    if mode == "2":
        return values

    if mode == "3":
        pos_value = float(input(f"{prefix}Размер позиции в деньгах: ").strip())
        pct = input(f"{prefix}Доходности в процентах? (y/n): ").strip().lower()
        returns_in_percent = pct in {"y", "yes", "д", "да"}
        return pnl_from_returns(values, pos_value, returns_in_percent)

    raise ValueError("Нужно выбрать режим 1, 2 или 3.")


def ask_portfolio_pnl() -> list[float]:
    mode = input("Источник P&L: 1) один ряд, 2) портфель (несколько рядов). Введите 1 или 2: ").strip()
    if mode == "1":
        return ask_single_series_pnl()

    if mode == "2":
        count_raw = input("Сколько рядов/инструментов в портфеле: ").strip()
        try:
            count = int(count_raw)
        except ValueError as exc:
            raise ValueError("Количество инструментов должно быть целым числом.") from exc
        if count <= 0:
            raise ValueError("Количество инструментов должно быть > 0.")

        print(
            "Для каждого инструмента задается вес/номинал агрегации. "
            "Итоговый портфельный P&L = сумма(weight_i * P&L_i)."
        )

        series_list: list[list[float]] = []
        for i in range(1, count + 1):
            instrument_pnl = ask_single_series_pnl(instrument_label=f"Инструмент {i}")
            weight_raw = input(
                f"[Инструмент {i}] Вес/номинал для агрегации (по умолчанию 1): "
            ).strip()
            weight = float(weight_raw) if weight_raw else 1.0
            series_list.append([weight * x for x in instrument_pnl])
        return aggregate_pnl_series(series_list)

    raise ValueError("Нужно выбрать 1 или 2.")


def run_historical_block() -> None:
    confidence = ask_confidence()
    pnl = ask_portfolio_pnl()

    var_loss, var_pnl, k = historical_var_discrete(pnl, confidence)
    es_loss, es_pnl, tail_count = expected_shortfall_discrete(pnl, confidence)

    print("\nSign convention:")
    print("- P&L < 0 означает убыток")
    print("- VaR и ES показываются как положительная величина потерь")

    print(f"\nHistorical VaR ({int(confidence * 100)}%, discrete, no interpolation): {var_loss:,.2f}")
    print(f"Опорный P&L (ceil(n*alpha)-й худший): {var_pnl:,.2f}; k={k}")
    print(f"Expected Shortfall ({int(confidence * 100)}%): {es_loss:,.2f}")
    print(f"Средний P&L в tail ({tail_count} худших наблюдений): {es_pnl:,.2f}")


def run_parametric_block() -> None:
    confidence = ask_confidence()
    pnl = ask_portfolio_pnl()

    var_loss, q_alpha_pnl, mu, sigma = parametric_var(pnl, confidence)
    z = z_value_for_confidence(confidence)

    print("\nSign convention:")
    print("- P&L < 0 означает убыток")
    print("- VaR показывается как положительная величина потерь")

    print(f"\nParametric VaR ({int(confidence * 100)}%, one-tailed): {var_loss:,.2f}")
    print(f"z-value (one-tailed): {z:.3f}")
    print(f"mu(P&L): {mu:,.4f}; sigma(P&L): {sigma:,.4f}")
    print(f"Левый квантиль P&L: {q_alpha_pnl:,.4f}")


def run_lvar_block() -> None:
    confidence = ask_confidence()
    pnl = ask_portfolio_pnl()

    base_method = input("Базовый VaR для LVaR: 1) historical, 2) parametric: ").strip()
    if base_method == "1":
        base_var, _, _ = historical_var_discrete(pnl, confidence)
        base_label = "Historical VaR"
    elif base_method == "2":
        base_var, _, _, _ = parametric_var(pnl, confidence)
        base_label = "Parametric VaR"
    else:
        raise ValueError("Нужно выбрать 1 или 2.")

    mid = float(input("Mid-market value позиции: ").strip())
    spread = float(input("Bid-Ask spread в %: ").strip())
    sigma_spread = float(input("Волатильность спреда (sigma spread) в %: ").strip())

    lc_normal = normal_liquidation_cost(mid, spread)
    lc_stressed = stressed_liquidation_cost(mid, spread, confidence, sigma_spread)

    print(f"\nБаза для LVaR: {base_label} = {base_var:,.2f}")
    print(f"Normal LC: {lc_normal:,.2f}")
    print(f"Stressed LC: {lc_stressed:,.2f}")
    print(f"LVaR (normal market): {base_var + lc_normal:,.2f}")
    print(f"LVaR (stressed market): {base_var + lc_stressed:,.2f}")


def run_linear_unwind_block() -> None:
    print("Модель: равномерная ликвидация позиции (linear unwind) за T дней.")
    print("Используется формула из конспекта: VaR_unwind = VaR_base / sqrt(((1+T)(1+2T))/(6T)).")

    base_var = float(input("Введите базовый VaR (до linear unwind): ").strip())
    days = int(input("Период ликвидации T (дней): ").strip())

    factor = linear_unwind_adjustment_factor(days)
    adjusted = linear_unwind_adjusted_var(base_var, days)

    print(f"Фактор linear unwind: {factor:.6f}")
    print(f"VaR с учетом равномерного выхода: {adjusted:,.2f}")


def run_calculator() -> None:
    print("=== Риск-калькулятор ===")
    print("1. Historical VaR + Expected Shortfall (discrete)")
    print("2. Parametric VaR (one-tailed)")
    print("3. LC (Normal + Stressed) и LVaR")
    print("4. Коррекция VaR на период ликвидации (linear unwind)")
    choice = input("Выберите пункт (1-4): ").strip()

    if choice == "1":
        run_historical_block()
        return

    if choice == "2":
        run_parametric_block()
        return

    if choice == "3":
        run_lvar_block()
        return

    if choice == "4":
        run_linear_unwind_block()
        return

    raise ValueError("Нужно выбрать пункт 1, 2, 3 или 4.")


if __name__ == "__main__":
    try:
        run_calculator()
    except Exception as exc:
        print(f"Ошибка: {exc}")
