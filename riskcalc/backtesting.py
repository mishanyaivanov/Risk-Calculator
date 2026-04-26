import math
from statistics import mean


def _safe_log_probability(probability: float) -> float:
    eps = 1e-12
    clipped = min(max(probability, eps), 1.0 - eps)
    return math.log(clipped)


def _chi2_sf_df1(statistic: float) -> float:
    if statistic <= 0.0:
        return 1.0
    return math.erfc(math.sqrt(statistic / 2.0))


def _chi2_sf_df2(statistic: float) -> float:
    if statistic <= 0.0:
        return 1.0
    return math.exp(-statistic / 2.0)


def _validate_confidence(confidence: float) -> None:
    if confidence <= 0.0 or confidence >= 1.0:
        raise ValueError("confidence должен быть в диапазоне (0, 1).")


def rolling_historical_var_es(
    pnl: list[float],
    confidence: float,
    window: int,
) -> dict[str, list[float] | list[bool]]:
    if len(pnl) <= window:
        raise ValueError("Длина ряда P&L должна быть больше окна rolling-backtest.")
    if window < 20:
        raise ValueError("Окно backtest должно быть не меньше 20 наблюдений.")
    _validate_confidence(confidence)

    alpha = 1.0 - confidence
    realized_pnl: list[float] = []
    var_losses: list[float] = []
    var_pnl_thresholds: list[float] = []
    es_losses: list[float] = []
    es_pnl_values: list[float] = []
    exceptions: list[bool] = []

    for idx in range(window, len(pnl)):
        train = sorted(pnl[idx - window:idx])
        n = len(train)
        k = max(1, math.ceil(n * alpha))
        tail = train[:k]
        var_pnl = train[k - 1]
        es_pnl = sum(tail) / k
        realized = pnl[idx]

        realized_pnl.append(realized)
        var_pnl_thresholds.append(var_pnl)
        var_losses.append(max(0.0, -var_pnl))
        es_pnl_values.append(es_pnl)
        es_losses.append(max(0.0, -es_pnl))
        exceptions.append(realized < var_pnl)

    return {
        "realized_pnl": realized_pnl,
        "var_losses": var_losses,
        "var_pnl_thresholds": var_pnl_thresholds,
        "es_losses": es_losses,
        "es_pnl_values": es_pnl_values,
        "exceptions": exceptions,
    }


def kupiec_pof_test(exceptions: list[bool], alpha: float) -> dict[str, float | int | str]:
    if not exceptions:
        raise ValueError("Для Kupiec test нужен непустой ряд исключений.")
    if alpha <= 0.0 or alpha >= 1.0:
        raise ValueError("alpha должен быть в диапазоне (0, 1).")

    n = len(exceptions)
    x = sum(1 for flag in exceptions if flag)
    p_hat = x / n

    log_l_restricted = (n - x) * _safe_log_probability(1.0 - alpha) + x * _safe_log_probability(alpha)
    log_l_unrestricted = (n - x) * _safe_log_probability(1.0 - p_hat) + x * _safe_log_probability(p_hat)
    lr_pof = max(0.0, -2.0 * (log_l_restricted - log_l_unrestricted))
    p_value = _chi2_sf_df1(lr_pof)

    if p_value < 0.01:
        verdict = "red"
    elif p_value < 0.05:
        verdict = "yellow"
    else:
        verdict = "green"

    return {
        "observations": n,
        "exceptions": x,
        "expected_exceptions": alpha * n,
        "exception_rate": p_hat,
        "lr_pof": lr_pof,
        "p_value": p_value,
        "verdict": verdict,
    }


def christoffersen_independence_test(
    exceptions: list[bool],
) -> dict[str, float | int | str]:
    if len(exceptions) < 2:
        raise ValueError("Для Christoffersen test нужно минимум 2 наблюдения.")

    n00 = n01 = n10 = n11 = 0
    prev = 1 if exceptions[0] else 0
    for current_flag in exceptions[1:]:
        current = 1 if current_flag else 0
        if prev == 0 and current == 0:
            n00 += 1
        elif prev == 0 and current == 1:
            n01 += 1
        elif prev == 1 and current == 0:
            n10 += 1
        else:
            n11 += 1
        prev = current

    total = n00 + n01 + n10 + n11
    if total == 0:
        raise ValueError("Недостаточно данных для оценки переходов исключений.")

    pi = (n01 + n11) / total
    pi0_den = n00 + n01
    pi1_den = n10 + n11
    pi0 = (n01 / pi0_den) if pi0_den > 0 else 0.0
    pi1 = (n11 / pi1_den) if pi1_den > 0 else 0.0

    log_l_null = (n00 + n10) * _safe_log_probability(1.0 - pi) + (n01 + n11) * _safe_log_probability(pi)
    log_l_alt = (
        n00 * _safe_log_probability(1.0 - pi0)
        + n01 * _safe_log_probability(pi0)
        + n10 * _safe_log_probability(1.0 - pi1)
        + n11 * _safe_log_probability(pi1)
    )
    lr_ind = max(0.0, -2.0 * (log_l_null - log_l_alt))
    p_value = _chi2_sf_df1(lr_ind)

    if p_value < 0.01:
        verdict = "red"
    elif p_value < 0.05:
        verdict = "yellow"
    else:
        verdict = "green"

    return {
        "n00": n00,
        "n01": n01,
        "n10": n10,
        "n11": n11,
        "pi0": pi0,
        "pi1": pi1,
        "lr_ind": lr_ind,
        "p_value": p_value,
        "verdict": verdict,
    }


def christoffersen_conditional_coverage_test(
    exceptions: list[bool],
    alpha: float,
) -> dict[str, float | int | str]:
    pof = kupiec_pof_test(exceptions, alpha)
    ind = christoffersen_independence_test(exceptions)
    lr_cc = float(pof["lr_pof"]) + float(ind["lr_ind"])
    p_value = _chi2_sf_df2(lr_cc)

    if p_value < 0.01:
        verdict = "red"
    elif p_value < 0.05:
        verdict = "yellow"
    else:
        verdict = "green"

    return {
        "lr_cc": lr_cc,
        "p_value": p_value,
        "verdict": verdict,
        "pof": pof,
        "independence": ind,
    }


def es_realized_shortfall_diagnostics(
    realized_pnl: list[float],
    var_pnl_thresholds: list[float],
    es_losses: list[float],
) -> dict[str, float]:
    if not realized_pnl:
        raise ValueError("Ряд realized P&L не может быть пустым.")
    if len(realized_pnl) != len(var_pnl_thresholds) or len(realized_pnl) != len(es_losses):
        raise ValueError("Длины рядов для ES diagnostics должны совпадать.")

    tail_losses: list[float] = []
    predicted_es_on_breach: list[float] = []
    for pnl_value, var_pnl, es_loss in zip(realized_pnl, var_pnl_thresholds, es_losses):
        if pnl_value < var_pnl:
            tail_losses.append(-pnl_value)
            predicted_es_on_breach.append(es_loss)

    if not tail_losses:
        return {
            "tail_events": 0.0,
            "avg_realized_tail_loss": 0.0,
            "avg_predicted_es": 0.0,
            "tail_loss_ratio": 0.0,
            "tail_bias": 0.0,
        }

    avg_realized = mean(tail_losses)
    avg_predicted = mean(predicted_es_on_breach)
    ratio = (avg_realized / avg_predicted) if avg_predicted > 0 else 0.0
    bias = avg_realized - avg_predicted
    return {
        "tail_events": float(len(tail_losses)),
        "avg_realized_tail_loss": avg_realized,
        "avg_predicted_es": avg_predicted,
        "tail_loss_ratio": ratio,
        "tail_bias": bias,
    }
