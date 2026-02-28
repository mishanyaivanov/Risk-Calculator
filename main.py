import math
from statistics import mean, stdev

from riskcalc.option_pricing import (
    black_scholes_price_and_greeks,
    normalize_option_type,
)
from riskcalc.option_var import (
    covariance_from_sigmas_and_correlation,
    option_var_moment_approximations,
    option_var_moment_approximations_multifactor,
    simulate_delta_gamma_pnl,
    simulate_delta_gamma_pnl_multifactor,
    simulate_full_revaluation_pnl,
    simulate_full_revaluation_pnl_multifactor,
)

# One-tailed z-values for left-tail VaR at supported confidence levels.
Z_BY_CONFIDENCE = {
    0.95: 1.645,
    0.99: 2.326,
}


def parse_float_number(raw: str, label: str) -> float:
    text = raw.strip().replace(",", ".")
    try:
        return float(text)
    except ValueError as exc:
        raise ValueError(f"{label} должно быть числом.") from exc


def parse_percent_or_decimal(raw: str, label: str) -> float:
    text = raw.strip().replace(",", ".")
    has_percent_suffix = text.endswith("%")
    if has_percent_suffix:
        text = text[:-1].strip()

    try:
        value = float(text)
    except ValueError as exc:
        raise ValueError(f"{label} должно быть числом (например, 5, 0.05 или 5%).") from exc

    if has_percent_suffix or abs(value) >= 1:
        value = value / 100.0
    return value


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


def ask_option_position(instrument_label: str = "") -> dict[str, float | str]:
    prefix = f"[{instrument_label}] " if instrument_label else ""
    underlying_raw = input(
        f"{prefix}Код underlying (например, AAPL, SPX; по умолчанию U1): "
    ).strip()
    underlying_id = underlying_raw if underlying_raw else "U1"
    option_type = normalize_option_type(
        input(f"{prefix}Тип опциона (call/c или put/p): ").strip()
    )
    spot = parse_float_number(input(f"{prefix}Spot S: ").strip(), "Spot S")
    strike = parse_float_number(input(f"{prefix}Strike K: ").strip(), "Strike K")
    maturity = parse_float_number(input(f"{prefix}Срок до экспирации T (в годах): ").strip(), "Срок T")
    rate = parse_percent_or_decimal(
        input(f"{prefix}Безрисковая ставка r (например, 5 или 0.05): ").strip(),
        "Ставка r",
    )
    vol = parse_percent_or_decimal(
        input(f"{prefix}Волатильность sigma (например, 20 или 0.20): ").strip(),
        "Волатильность sigma",
    )
    div_raw = input(f"{prefix}Dividend yield q (по умолчанию 0): ").strip()
    dividend = parse_percent_or_decimal(div_raw, "Dividend yield q") if div_raw else 0.0

    qty_raw = input(f"{prefix}Количество опционов (можно отрицательное, по умолчанию 1): ").strip()
    quantity = parse_float_number(qty_raw, "Количество опционов") if qty_raw else 1.0

    mult_raw = input(f"{prefix}Contract multiplier (по умолчанию 1): ").strip()
    multiplier = parse_float_number(mult_raw, "Contract multiplier") if mult_raw else 1.0

    return {
        "underlying_id": underlying_id,
        "option_type": option_type,
        "spot": spot,
        "strike": strike,
        "maturity_years": maturity,
        "rate": rate,
        "volatility": vol,
        "dividend_yield": dividend,
        "quantity": quantity,
        "multiplier": multiplier,
    }


def ask_option_positions() -> list[dict[str, float | str]]:
    mode = input("Режим: 1) один опцион, 2) портфель опционов. Введите 1 или 2: ").strip()

    positions: list[dict[str, float | str]] = []
    if mode == "1":
        positions.append(ask_option_position())
        return positions

    if mode == "2":
        count_raw = input("Сколько опционных позиций в портфеле: ").strip()
        try:
            count = int(count_raw)
        except ValueError as exc:
            raise ValueError("Количество позиций должно быть целым числом.") from exc
        if count <= 0:
            raise ValueError("Количество позиций должно быть > 0.")

        for i in range(1, count + 1):
            print(f"\nПозиция {i}:")
            positions.append(ask_option_position(instrument_label=f"Позиция {i}"))
        return positions

    raise ValueError("Нужно выбрать 1 или 2.")


def evaluate_option_position(position: dict[str, float | str]) -> dict[str, float | str]:
    greeks = black_scholes_price_and_greeks(
        option_type=str(position["option_type"]),
        spot=float(position["spot"]),
        strike=float(position["strike"]),
        maturity_years=float(position["maturity_years"]),
        rate=float(position["rate"]),
        volatility=float(position["volatility"]),
        dividend_yield=float(position["dividend_yield"]),
    )

    spot = float(position["spot"])
    scale = float(position["quantity"]) * float(position["multiplier"])
    theta_day = greeks["theta"] * scale / 365.0

    return {
        "underlying_id": str(position.get("underlying_id", "U1")),
        "option_type": str(position["option_type"]),
        "spot": spot,
        "scale": scale,
        "d1": greeks["d1"],
        "d2": greeks["d2"],
        "price": greeks["price"],
        "delta": greeks["delta"] * scale,
        "gamma": greeks["gamma"] * scale,
        "vega": greeks["vega"] * scale,
        "theta": greeks["theta"] * scale,
        "rho": greeks["rho"] * scale,
        "value": greeks["price"] * scale,
        # Cash Greeks for dS = S * return shock, useful for VaR approximations.
        "delta_cash": greeks["delta"] * spot * scale,
        "gamma_cash": greeks["gamma"] * (spot ** 2) * scale,
        "theta_day": theta_day,
    }


def aggregate_option_results(evaluated_positions: list[dict[str, float | str]]) -> dict[str, float]:
    totals = {
        "value": 0.0,
        "delta": 0.0,
        "gamma": 0.0,
        "vega": 0.0,
        "theta": 0.0,
        "rho": 0.0,
        "delta_cash": 0.0,
        "gamma_cash": 0.0,
        "theta_day": 0.0,
    }
    for row in evaluated_positions:
        totals["value"] += float(row["value"])
        totals["delta"] += float(row["delta"])
        totals["gamma"] += float(row["gamma"])
        totals["vega"] += float(row["vega"])
        totals["theta"] += float(row["theta"])
        totals["rho"] += float(row["rho"])
        totals["delta_cash"] += float(row["delta_cash"])
        totals["gamma_cash"] += float(row["gamma_cash"])
        totals["theta_day"] += float(row["theta_day"])
    return totals


def aggregate_cash_exposures_by_underlying(
    evaluated_positions: list[dict[str, float | str]]
) -> dict[str, dict[str, float]]:
    exposures: dict[str, dict[str, float]] = {}
    for row in evaluated_positions:
        underlying = str(row.get("underlying_id", "U1"))
        if underlying not in exposures:
            exposures[underlying] = {"delta_cash": 0.0, "gamma_cash": 0.0}
        exposures[underlying]["delta_cash"] += float(row["delta_cash"])
        exposures[underlying]["gamma_cash"] += float(row["gamma_cash"])
    return exposures


def ordered_underlyings_from_positions(positions: list[dict[str, float | str]]) -> list[str]:
    underlyings: list[str] = []
    for position in positions:
        underlying = str(position.get("underlying_id", "U1"))
        if underlying not in underlyings:
            underlyings.append(underlying)
    return underlyings


def correlation_matrix_from_return_series(series_list: list[list[float]]) -> list[list[float]]:
    if not series_list:
        raise ValueError("Нужно минимум 1 ряд доходностей.")
    n = len(series_list)
    obs = len(series_list[0])
    if obs < 2:
        raise ValueError("В каждом ряду доходностей должно быть минимум 2 наблюдения.")
    for idx, series in enumerate(series_list, start=1):
        if len(series) != obs:
            raise ValueError(
                f"Ряды доходностей должны быть одной длины. Ряд 1: {obs}, ряд {idx}: {len(series)}."
            )

    means = [mean(series) for series in series_list]
    stds = [stdev(series) for series in series_list]
    matrix = [[0.0 for _ in range(n)] for _ in range(n)]

    for i in range(n):
        matrix[i][i] = 1.0
        for j in range(i + 1, n):
            cov = 0.0
            for k in range(obs):
                cov += (series_list[i][k] - means[i]) * (series_list[j][k] - means[j])
            cov /= (obs - 1)

            if stds[i] == 0.0 or stds[j] == 0.0:
                corr = 0.0
            else:
                corr = cov / (stds[i] * stds[j])
                corr = max(-1.0, min(1.0, corr))
            matrix[i][j] = corr
            matrix[j][i] = corr
    return matrix


def ask_return_distribution_params() -> tuple[float, float]:
    print("Параметры доходности базового актива (дневные):")
    print("1. Оценить mu и sigma по историческому ряду доходностей")
    print("2. Ввести mu и sigma вручную")
    mode = input("Выберите режим (1-2): ").strip()

    if mode == "1":
        raw = input("Вставьте дневные доходности через запятую: ").strip()
        values = parse_number_list(raw)
        pct = input("Доходности в процентах? (y/n): ").strip().lower()
        in_percent = pct in {"y", "yes", "д", "да"}
        scale = 0.01 if in_percent else 1.0
        returns = [x * scale for x in values]
        mu = mean(returns)
        sigma = stdev(returns)
        if sigma < 0:
            raise ValueError("sigma не может быть отрицательной.")
        print(f"Оценка по истории: mu={mu:.6f}, sigma={sigma:.6f}")
        return mu, sigma

    if mode == "2":
        mu = parse_percent_or_decimal(
            input("Введите дневную ожидаемую доходность mu (например, 0.05 или 5%): ").strip(),
            "mu",
        )
        sigma = parse_percent_or_decimal(
            input("Введите дневную волатильность sigma (например, 0.02 или 2%): ").strip(),
            "sigma",
        )
        if sigma < 0:
            raise ValueError("sigma не может быть отрицательной.")
        return mu, sigma

    raise ValueError("Нужно выбрать 1 или 2.")


def ask_multifactor_distribution_params(
    underlying_order: list[str],
) -> tuple[list[float], list[float], list[list[float]]]:
    if not underlying_order:
        raise ValueError("Нужен хотя бы один underlying.")

    print("\nПараметры по underlying (мультифакторно):")
    print(f"Список факторов: {', '.join(underlying_order)}")
    print("1. Ввести mu/sigma вручную + корреляции вручную")
    print("2. Оценить mu/sigma/correlation по историческим рядам доходностей")
    mode = input("Выберите режим (1-2): ").strip()

    if mode == "1":
        mu_daily: list[float] = []
        sigma_daily: list[float] = []
        for name in underlying_order:
            print(f"\n[{name}]")
            mu_i = parse_percent_or_decimal(
                input("Дневной mu (например, 0.05 или 5%): ").strip(),
                f"mu для {name}",
            )
            sigma_i = parse_percent_or_decimal(
                input("Дневной sigma (например, 0.02 или 2%): ").strip(),
                f"sigma для {name}",
            )
            if sigma_i < 0:
                raise ValueError("Sigma не может быть отрицательной.")
            mu_daily.append(mu_i)
            sigma_daily.append(sigma_i)

        n = len(underlying_order)
        corr = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
        for i in range(n):
            for j in range(i + 1, n):
                raw = input(
                    f"Корреляция rho({underlying_order[i]}, {underlying_order[j]}) "
                    "(по умолчанию 0): "
                ).strip()
                rho = parse_float_number(raw, "Корреляция rho") if raw else 0.0
                if rho < -1.0 or rho > 1.0:
                    raise ValueError("Корреляция должна быть в диапазоне [-1, 1].")
                corr[i][j] = rho
                corr[j][i] = rho
        return mu_daily, sigma_daily, corr

    if mode == "2":
        pct = input("Доходности в процентах? (y/n): ").strip().lower()
        in_percent = pct in {"y", "yes", "д", "да"}
        scale = 0.01 if in_percent else 1.0

        series_list: list[list[float]] = []
        for name in underlying_order:
            raw = input(
                f"[{name}] Вставьте ряд дневных доходностей через запятую: "
            ).strip()
            values = parse_number_list(raw)
            returns = [x * scale for x in values]
            series_list.append(returns)

        mu_daily = [mean(series) for series in series_list]
        sigma_daily = [stdev(series) for series in series_list]
        corr = correlation_matrix_from_return_series(series_list)

        print("\nОценки по истории:")
        for i, name in enumerate(underlying_order):
            print(f"- {name}: mu={mu_daily[i]:.6f}, sigma={sigma_daily[i]:.6f}")
        return mu_daily, sigma_daily, corr

    raise ValueError("Нужно выбрать 1 или 2.")


def ask_full_revaluation_extra_shocks() -> dict[str, float]:
    print("\nДополнительные шоки для Full Revaluation MC (на весь горизонт VaR):")
    use_vol_raw = input("Добавить шок implied volatility? (y/n, по умолчанию n): ").strip().lower()
    use_vol = use_vol_raw in {"y", "yes", "д", "да"}

    vol_mean_horizon = 0.0
    vol_sigma_horizon = 0.0
    if use_vol:
        vol_mean_horizon = parse_percent_or_decimal(
            input("Средний vol-shock (additive, напр. +1% = 1 или 0.01): ").strip(),
            "Средний vol-shock",
        )
        vol_sigma_horizon = parse_percent_or_decimal(
            input("Sigma vol-shock (additive, напр. 2% = 2 или 0.02): ").strip(),
            "Sigma vol-shock",
        )
        if vol_sigma_horizon < 0:
            raise ValueError("Sigma vol-shock не может быть отрицательной.")

    use_rate_raw = input("Добавить шок процентной ставки r? (y/n, по умолчанию n): ").strip().lower()
    use_rate = use_rate_raw in {"y", "yes", "д", "да"}

    rate_mean_horizon = 0.0
    rate_sigma_horizon = 0.0
    if use_rate:
        rate_mean_horizon = parse_percent_or_decimal(
            input("Средний rate-shock (additive, напр. +25 bps = 0.0025 или 0.25%): ").strip(),
            "Средний rate-shock",
        )
        rate_sigma_horizon = parse_percent_or_decimal(
            input("Sigma rate-shock (напр. 20 bps = 0.0020 или 0.20%): ").strip(),
            "Sigma rate-shock",
        )
        if rate_sigma_horizon < 0:
            raise ValueError("Sigma rate-shock не может быть отрицательной.")

    return {
        "vol_mean_horizon": vol_mean_horizon,
        "vol_sigma_horizon": vol_sigma_horizon,
        "rate_mean_horizon": rate_mean_horizon,
        "rate_sigma_horizon": rate_sigma_horizon,
    }


def run_options_greeks_block() -> None:
    print("Модель: Black-Scholes-Merton для европейских опционов.")
    positions = ask_option_positions()
    evaluated = [evaluate_option_position(position) for position in positions]
    totals = aggregate_option_results(evaluated)
    by_underlying = aggregate_cash_exposures_by_underlying(evaluated)

    for idx, row in enumerate(evaluated, start=1):
        scale = float(row["scale"])
        print(
            f"\n--- Позиция {idx} "
            f"({row['option_type']}, underlying={row['underlying_id']}) ---"
        )
        print(f"d1={float(row['d1']):.6f}, d2={float(row['d2']):.6f}")
        print(f"Цена за 1 опцион: {float(row['price']):,.6f}")
        print(
            f"Позиция (qty*mult={scale:,.4f}): value={float(row['value']):,.4f}, "
            f"delta={float(row['delta']):,.6f}, gamma={float(row['gamma']):,.6f}, "
            f"vega={float(row['vega']):,.6f}, theta/day={float(row['theta_day']):,.6f}, rho={float(row['rho']):,.6f}"
        )
        print(
            f"Cash Greeks (на доходность базового актива): "
            f"delta_cash={float(row['delta_cash']):,.6f}, gamma_cash={float(row['gamma_cash']):,.6f}"
        )

    print("\n=== Итого по портфелю ===")
    print(f"Портфельная стоимость: {totals['value']:,.4f}")
    print(f"Delta: {totals['delta']:,.6f}")
    print(f"Gamma: {totals['gamma']:,.6f}")
    print(f"Vega: {totals['vega']:,.6f} (на +1% vol: {totals['vega'] * 0.01:,.6f})")
    print(f"Theta/year: {totals['theta']:,.6f} (theta/day: {totals['theta'] / 365.0:,.6f})")
    print(f"Rho: {totals['rho']:,.6f} (на +1% ставки: {totals['rho'] * 0.01:,.6f})")
    print(f"Delta_cash: {totals['delta_cash']:,.6f}; Gamma_cash: {totals['gamma_cash']:,.6f}")
    print("Cash-exposures по underlying:")
    for underlying, exposure in by_underlying.items():
        print(
            f"- {underlying}: delta_cash={exposure['delta_cash']:,.6f}, "
            f"gamma_cash={exposure['gamma_cash']:,.6f}"
        )


def run_option_var_block() -> None:
    print(
        "Option VaR: Delta-Normal, Delta-Gamma и Full Revaluation MC "
        "(европейские опционы BSM, с optional vol/rate shocks)."
    )
    confidence = ask_confidence()
    z = z_value_for_confidence(confidence)

    print("\nСначала задаем портфель опционов для оценки Greeks.")
    positions = ask_option_positions()
    evaluated = [evaluate_option_position(position) for position in positions]
    totals = aggregate_option_results(evaluated)
    exposures_by_underlying = aggregate_cash_exposures_by_underlying(evaluated)
    underlying_order = ordered_underlyings_from_positions(positions)

    days_raw = input("Горизонт VaR в днях (например, 1 или 10): ").strip()
    try:
        horizon_days = int(days_raw)
    except ValueError as exc:
        raise ValueError("Горизонт VaR должен быть целым числом дней.") from exc
    if horizon_days <= 0:
        raise ValueError("Горизонт VaR должен быть > 0.")

    include_theta_raw = input("Учитывать theta decay на горизонте? (y/n, по умолчанию y): ").strip().lower()
    include_theta = include_theta_raw not in {"n", "no", "н", "нет"}
    theta_horizon = totals["theta_day"] * horizon_days if include_theta else 0.0

    multifactor = False
    if len(underlying_order) > 1:
        print("\nРежим шоков факторов:")
        print("1. Однофакторный (один общий шок доходности для всех positions)")
        print("2. Мультифакторный (по каждому underlying + корреляции)")
        shock_mode = input("Выберите режим (1-2, по умолчанию 2): ").strip()
        multifactor = shock_mode != "1"
    else:
        print("\nВ портфеле один underlying: используется однофакторный режим.")

    if not multifactor:
        mu_daily, sigma_daily = ask_return_distribution_params()
        mu_horizon = mu_daily * horizon_days
        sigma_horizon = sigma_daily * math.sqrt(horizon_days)

        approximations = option_var_moment_approximations(
            delta_cash=totals["delta_cash"],
            gamma_cash=totals["gamma_cash"],
            theta_horizon=theta_horizon,
            mu_horizon=mu_horizon,
            sigma_horizon=sigma_horizon,
            z_value=z,
        )

        print("\nПараметры модели:")
        print(f"- режим: однофакторный")
        print(f"- confidence={int(confidence * 100)}%")
        print(f"- mu_daily={mu_daily:.6f}, sigma_daily={sigma_daily:.6f}")
        print(
            f"- horizon_days={horizon_days}, "
            f"mu_horizon={mu_horizon:.6f}, sigma_horizon={sigma_horizon:.6f}"
        )
        print(f"- include_theta={include_theta}, theta_horizon={theta_horizon:,.6f}")
        print(
            f"- delta_cash={totals['delta_cash']:,.6f}, "
            f"gamma_cash={totals['gamma_cash']:,.6f}"
        )
    else:
        mu_daily_vec, sigma_daily_vec, corr_matrix = ask_multifactor_distribution_params(
            underlying_order
        )
        mu_horizon_vec = [x * horizon_days for x in mu_daily_vec]
        sigma_horizon_vec = [x * math.sqrt(horizon_days) for x in sigma_daily_vec]
        covariance_horizon = covariance_from_sigmas_and_correlation(
            sigma_values=sigma_horizon_vec,
            correlation_matrix=corr_matrix,
        )

        delta_cash_vec = [
            exposures_by_underlying[name]["delta_cash"] for name in underlying_order
        ]
        gamma_cash_vec = [
            exposures_by_underlying[name]["gamma_cash"] for name in underlying_order
        ]

        approximations = option_var_moment_approximations_multifactor(
            delta_cash_values=delta_cash_vec,
            gamma_cash_values=gamma_cash_vec,
            theta_horizon=theta_horizon,
            mu_horizon_values=mu_horizon_vec,
            covariance_horizon=covariance_horizon,
            z_value=z,
        )

        print("\nПараметры модели:")
        print(f"- режим: мультифакторный")
        print(f"- confidence={int(confidence * 100)}%")
        print(f"- horizon_days={horizon_days}")
        print(f"- include_theta={include_theta}, theta_horizon={theta_horizon:,.6f}")
        print("- факторы и экспозиции:")
        for idx, name in enumerate(underlying_order):
            print(
                f"  {name}: mu_daily={mu_daily_vec[idx]:.6f}, "
                f"sigma_daily={sigma_daily_vec[idx]:.6f}, "
                f"delta_cash={delta_cash_vec[idx]:,.6f}, "
                f"gamma_cash={gamma_cash_vec[idx]:,.6f}"
            )

    print("\nDelta-Normal VaR:")
    print(f"- mu(PnL)={approximations['mu_dn']:,.6f}")
    print(f"- sigma(PnL)={approximations['sigma_dn']:,.6f}")
    print(f"- q_alpha(PnL)={approximations['q_dn']:,.6f}")
    print(f"- VaR={approximations['var_dn']:,.6f}")

    print("\nDelta-Gamma VaR (moment-matching normal approximation):")
    print(f"- mu(PnL)={approximations['mu_dg']:,.6f}")
    print(f"- sigma(PnL)={approximations['sigma_dg']:,.6f}")
    print(f"- q_alpha(PnL)={approximations['q_dg']:,.6f}")
    print(f"- VaR={approximations['var_dg']:,.6f}")

    run_dg_mc_raw = input(
        "\nСчитать Delta-Gamma VaR через Monte Carlo? (y/n, по умолчанию y): "
    ).strip().lower()
    run_dg_mc = run_dg_mc_raw not in {"n", "no", "н", "нет"}
    run_full_mc_raw = input(
        "Считать Full Revaluation Monte Carlo? (y/n, по умолчанию y): "
    ).strip().lower()
    run_full_mc = run_full_mc_raw not in {"n", "no", "н", "нет"}

    if not run_dg_mc and not run_full_mc:
        return

    sims_raw = input("Количество симуляций (по умолчанию 50000): ").strip()
    simulations = int(sims_raw) if sims_raw else 50_000
    seed_raw = input("Seed (по умолчанию 42): ").strip()
    seed = int(seed_raw) if seed_raw else 42
    full_reval_shocks = {
        "vol_mean_horizon": 0.0,
        "vol_sigma_horizon": 0.0,
        "rate_mean_horizon": 0.0,
        "rate_sigma_horizon": 0.0,
    }
    if run_full_mc:
        full_reval_shocks = ask_full_revaluation_extra_shocks()

    if not multifactor:
        if run_dg_mc:
            pnl_dg_mc = simulate_delta_gamma_pnl(
                delta_cash=totals["delta_cash"],
                gamma_cash=totals["gamma_cash"],
                theta_horizon=theta_horizon,
                mu_horizon=mu_horizon,
                sigma_horizon=sigma_horizon,
                simulations=simulations,
                seed=seed,
            )
            var_loss, var_pnl, k = historical_var_discrete(pnl_dg_mc, confidence)
            es_loss, es_pnl, tail_count = expected_shortfall_discrete(pnl_dg_mc, confidence)

            print("\nDelta-Gamma Monte Carlo:")
            print(f"- scenarios={simulations}, seed={seed}")
            print(f"- VaR={var_loss:,.6f} (опорный PnL={var_pnl:,.6f}, k={k})")
            print(f"- ES={es_loss:,.6f} (tail mean PnL={es_pnl:,.6f}, tail_count={tail_count})")

        if run_full_mc:
            pnl_full_mc = simulate_full_revaluation_pnl(
                positions=positions,
                horizon_days=horizon_days,
                mu_horizon=mu_horizon,
                sigma_horizon=sigma_horizon,
                simulations=simulations,
                seed=seed,
                vol_mean_horizon=full_reval_shocks["vol_mean_horizon"],
                vol_sigma_horizon=full_reval_shocks["vol_sigma_horizon"],
                rate_mean_horizon=full_reval_shocks["rate_mean_horizon"],
                rate_sigma_horizon=full_reval_shocks["rate_sigma_horizon"],
            )
            var_loss, var_pnl, k = historical_var_discrete(pnl_full_mc, confidence)
            es_loss, es_pnl, tail_count = expected_shortfall_discrete(pnl_full_mc, confidence)

            print("\nFull Revaluation Monte Carlo:")
            print(f"- scenarios={simulations}, seed={seed}")
            print(
                "- extra shocks: "
                f"vol_mean={full_reval_shocks['vol_mean_horizon']:.6f}, "
                f"vol_sigma={full_reval_shocks['vol_sigma_horizon']:.6f}, "
                f"rate_mean={full_reval_shocks['rate_mean_horizon']:.6f}, "
                f"rate_sigma={full_reval_shocks['rate_sigma_horizon']:.6f}"
            )
            print(f"- VaR={var_loss:,.6f} (опорный PnL={var_pnl:,.6f}, k={k})")
            print(f"- ES={es_loss:,.6f} (tail mean PnL={es_pnl:,.6f}, tail_count={tail_count})")
        return

    if run_dg_mc:
        pnl_dg_mc = simulate_delta_gamma_pnl_multifactor(
            delta_cash_values=delta_cash_vec,
            gamma_cash_values=gamma_cash_vec,
            theta_horizon=theta_horizon,
            mean_vector=mu_horizon_vec,
            covariance_matrix=covariance_horizon,
            simulations=simulations,
            seed=seed,
        )
        var_loss, var_pnl, k = historical_var_discrete(pnl_dg_mc, confidence)
        es_loss, es_pnl, tail_count = expected_shortfall_discrete(pnl_dg_mc, confidence)

        print("\nDelta-Gamma Monte Carlo (multifactor):")
        print(f"- scenarios={simulations}, seed={seed}")
        print(f"- VaR={var_loss:,.6f} (опорный PnL={var_pnl:,.6f}, k={k})")
        print(f"- ES={es_loss:,.6f} (tail mean PnL={es_pnl:,.6f}, tail_count={tail_count})")

    if run_full_mc:
        pnl_full_mc = simulate_full_revaluation_pnl_multifactor(
            positions=positions,
            horizon_days=horizon_days,
            underlying_order=underlying_order,
            mean_vector=mu_horizon_vec,
            covariance_matrix=covariance_horizon,
            simulations=simulations,
            seed=seed,
            vol_mean_horizon=full_reval_shocks["vol_mean_horizon"],
            vol_sigma_horizon=full_reval_shocks["vol_sigma_horizon"],
            rate_mean_horizon=full_reval_shocks["rate_mean_horizon"],
            rate_sigma_horizon=full_reval_shocks["rate_sigma_horizon"],
        )
        var_loss, var_pnl, k = historical_var_discrete(pnl_full_mc, confidence)
        es_loss, es_pnl, tail_count = expected_shortfall_discrete(pnl_full_mc, confidence)

        print("\nFull Revaluation Monte Carlo (multifactor):")
        print(f"- scenarios={simulations}, seed={seed}")
        print(
            "- extra shocks: "
            f"vol_mean={full_reval_shocks['vol_mean_horizon']:.6f}, "
            f"vol_sigma={full_reval_shocks['vol_sigma_horizon']:.6f}, "
            f"rate_mean={full_reval_shocks['rate_mean_horizon']:.6f}, "
            f"rate_sigma={full_reval_shocks['rate_sigma_horizon']:.6f}"
        )
        print(f"- VaR={var_loss:,.6f} (опорный PnL={var_pnl:,.6f}, k={k})")
        print(f"- ES={es_loss:,.6f} (tail mean PnL={es_pnl:,.6f}, tail_count={tail_count})")


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
    print("5. Black-Scholes + Greeks (одна опция или портфель)")
    print("6. Option VaR: Delta-Normal, Delta-Gamma и Full Revaluation MC (+vol/rate)")
    choice = input("Выберите пункт (1-6): ").strip()

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

    if choice == "5":
        run_options_greeks_block()
        return

    if choice == "6":
        run_option_var_block()
        return

    raise ValueError("Нужно выбрать пункт 1, 2, 3, 4, 5 или 6.")


if __name__ == "__main__":
    try:
        run_calculator()
    except Exception as exc:
        print(f"Ошибка: {exc}")
