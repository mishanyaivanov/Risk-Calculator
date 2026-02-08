import math
from statistics import mean, stdev

Z_BY_CONFIDENCE = {
    0.95: 1.645,
    0.99: 2.326,
}


def parse_number_list(raw: str) -> list[float]:
    items = [x.strip() for x in raw.replace(";", ",").split(",") if x.strip()]
    if len(items) < 2:
        raise ValueError("Нужно минимум 2 числа.")
    return [float(x) for x in items]


def pnl_from_prices(prices: list[float]) -> list[float]:
    if len(prices) < 2:
        raise ValueError("Для расчета P&L нужно минимум 2 цены.")
    return [prices[i] - prices[i - 1] for i in range(1, len(prices))]


def historical_var(pnl: list[float], confidence: float) -> float:
    sorted_pnl = sorted(pnl)
    idx = math.ceil(len(sorted_pnl) * (1 - confidence)) - 1
    idx = max(0, min(idx, len(sorted_pnl) - 1))
    quantile_pnl = sorted_pnl[idx]
    return max(0.0, -quantile_pnl)


def parametric_var(pnl: list[float], confidence: float) -> float:
    if len(pnl) < 2:
        raise ValueError("Для параметрического VaR нужно минимум 2 значения P&L.")
    mu = mean(pnl)
    sigma = stdev(pnl)
    z = Z_BY_CONFIDENCE[confidence]
    return max(0.0, z * sigma - mu)


def normal_liquidation_cost(mid_market_value: float, spread_percent: float) -> float:
    return 0.5 * abs(mid_market_value) * (spread_percent / 100.0)


def stressed_liquidation_cost(
    mid_market_value: float,
    spread_percent: float,
    confidence: float,
    sigma_spread_percent: float,
) -> float:
    z = Z_BY_CONFIDENCE[confidence]
    s = spread_percent / 100.0
    sigma_s = sigma_spread_percent / 100.0
    return 0.5 * abs(mid_market_value) * (s + z * sigma_s)


def adjust_var_for_liquidation_period(var_1d: float, days: int) -> float:
    if days <= 0:
        raise ValueError("Период ликвидации T должен быть > 0.")
    factor = math.sqrt(((1 + days) * (1 + 2 * days)) / (6 * days))
    return var_1d / factor


def ask_confidence() -> float:
    value = input("Уровень доверия (95 или 99): ").strip()
    if value == "95":
        return 0.95
    if value == "99":
        return 0.99
    raise ValueError("Допустимы только 95 или 99.")


def ask_pnl() -> list[float]:
    mode = input("Данные: 1) ряд цен, 2) ряд P&L. Введите 1 или 2: ").strip()
    raw = input("Вставьте числа через запятую: ").strip()
    values = parse_number_list(raw)
    if mode == "1":
        return pnl_from_prices(values)
    if mode == "2":
        return values
    raise ValueError("Нужно выбрать 1 или 2.")


def run_calculator() -> None:
    print("=== Риск-калькулятор (базовый) ===")
    print("1. Historical VaR")
    print("2. Parametric VaR")
    print("3. LC (Normal + Stressed) и LVaR")
    print("4. Коррекция VaR на период ликвидации")
    choice = input("Выберите пункт (1-4): ").strip()

    if choice == "1":
        conf = ask_confidence()
        pnl = ask_pnl()
        var_value = historical_var(pnl, conf)
        print(f"Historical VaR ({int(conf * 100)}%, 1 день): {var_value:,.2f}")
        return

    if choice == "2":
        conf = ask_confidence()
        pnl = ask_pnl()
        var_value = parametric_var(pnl, conf)
        print(f"Parametric VaR ({int(conf * 100)}%, 1 день): {var_value:,.2f}")
        return

    if choice == "3":
        conf = ask_confidence()
        pnl = ask_pnl()
        base_var = historical_var(pnl, conf)

        mid = float(input("Mid-market value позиции: ").strip())
        spread = float(input("Bid-Ask spread в %: ").strip())
        sigma_spread = float(input("Волатильность спреда (sigma spread) в %: ").strip())

        lc_normal = normal_liquidation_cost(mid, spread)
        lc_stressed = stressed_liquidation_cost(mid, spread, conf, sigma_spread)
        lvar_normal = base_var + lc_normal
        lvar_stressed = base_var + lc_stressed

        print(f"Базовый VaR ({int(conf * 100)}%): {base_var:,.2f}")
        print(f"Normal LC: {lc_normal:,.2f}")
        print(f"Stressed LC: {lc_stressed:,.2f}")
        print(f"LVaR (normal market): {lvar_normal:,.2f}")
        print(f"LVaR (stressed market): {lvar_stressed:,.2f}")
        return

    if choice == "4":
        var_1d = float(input("VaR за 1 день: ").strip())
        days = int(input("Период ликвидации T (дней): ").strip())
        adjusted = adjust_var_for_liquidation_period(var_1d, days)
        print(f"VaR c учетом ликвидации за {days} дней: {adjusted:,.2f}")
        return

    raise ValueError("Нужно выбрать пункт 1, 2, 3 или 4.")


if __name__ == "__main__":
    try:
        run_calculator()
    except Exception as exc:
        print(f"Ошибка: {exc}")
