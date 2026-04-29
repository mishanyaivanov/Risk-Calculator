"""Bond issue and interest-rate swap spread selection.

The module is intentionally JSON-friendly: public functions accept plain
dictionaries/lists and return dictionaries with only primitive values.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Mapping, Sequence


DateLike = str | date | datetime
CurveItem = Mapping[str, Any] | Sequence[Any]


@dataclass(frozen=True)
class CurvePoint:
    tenor_years: float
    rate: float

    def as_dict(self) -> dict[str, float]:
        return {"tenor_years": self.tenor_years, "rate": self.rate}


@dataclass(frozen=True)
class BondIssue:
    issue_date: date
    maturity_date: date
    notional: float
    coupon_rate: float
    payment_frequency_months: int = 6
    day_count: str = "ACT/365"

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "BondIssue":
        return cls(
            issue_date=parse_date(raw["issue_date"]),
            maturity_date=parse_date(raw["maturity_date"]),
            notional=_positive_float(raw["notional"], "notional"),
            coupon_rate=parse_rate(raw["coupon_rate"]),
            payment_frequency_months=int(raw.get("payment_frequency_months", 6)),
            day_count=str(raw.get("day_count", "ACT/365")).upper(),
        )

    def validate(self) -> None:
        if self.maturity_date <= self.issue_date:
            raise ValueError("maturity_date must be later than issue_date.")
        if self.payment_frequency_months <= 0:
            raise ValueError("payment_frequency_months must be positive.")
        if 12 % self.payment_frequency_months != 0:
            raise ValueError("payment_frequency_months must divide 12.")
        if self.day_count != "ACT/365":
            raise ValueError("Only ACT/365 day count is supported in this version.")

    def as_dict(self) -> dict[str, Any]:
        return {
            "issue_date": self.issue_date.isoformat(),
            "maturity_date": self.maturity_date.isoformat(),
            "notional": self.notional,
            "coupon_rate": self.coupon_rate,
            "payment_frequency_months": self.payment_frequency_months,
            "day_count": self.day_count,
        }


@dataclass(frozen=True)
class BondCashflow:
    period_start: date
    period_end: date
    payment_date: date
    accrual_years: float
    coupon_cashflow: float
    principal_cashflow: float

    @property
    def total_cashflow(self) -> float:
        return self.coupon_cashflow + self.principal_cashflow

    def as_dict(self) -> dict[str, Any]:
        return {
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "payment_date": self.payment_date.isoformat(),
            "accrual_years": self.accrual_years,
            "coupon_cashflow": self.coupon_cashflow,
            "principal_cashflow": self.principal_cashflow,
            "total_cashflow": self.total_cashflow,
        }


def parse_date(raw: DateLike) -> date:
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    if isinstance(raw, str):
        return date.fromisoformat(raw.strip())
    raise TypeError("Date must be ISO string, date, or datetime.")


def parse_rate(raw: Any) -> float:
    value = float(str(raw).strip().replace("%", "").replace(",", "."))
    if "%" in str(raw) or abs(value) > 1.0:
        value /= 100.0
    return value


def tenor_to_years(raw: Any) -> float:
    if isinstance(raw, (int, float)):
        return float(raw)

    text = str(raw).strip().upper().replace(" ", "")
    if text in {"ON", "O/N", "0D", "TODAY"}:
        return 0.0
    if len(text) < 2:
        raise ValueError(f"Invalid tenor: {raw!r}.")

    unit = text[-1]
    number = float(text[:-1].replace(",", "."))
    if unit == "D":
        return number / 365.0
    if unit == "W":
        return number * 7.0 / 365.0
    if unit == "M":
        return number / 12.0
    if unit == "Y":
        return number
    raise ValueError(f"Unsupported tenor unit in {raw!r}.")


def normalize_curve_points(curve: Sequence[CurveItem]) -> list[CurvePoint]:
    if not curve:
        raise ValueError("curve must contain at least one point.")

    by_tenor: dict[float, float] = {}
    for item in curve:
        if isinstance(item, Mapping):
            tenor_raw = item.get("tenor_years", item.get("tenor"))
            if tenor_raw is None:
                raise ValueError("Curve point must contain tenor_years or tenor.")
            rate_raw = item["rate"]
        else:
            if len(item) < 2:
                raise ValueError("Curve tuple/list must contain tenor and rate.")
            tenor_raw, rate_raw = item[0], item[1]

        tenor = tenor_to_years(tenor_raw)
        if tenor < 0:
            raise ValueError("Curve tenor cannot be negative.")
        by_tenor[tenor] = parse_rate(rate_raw)

    return [CurvePoint(tenor, by_tenor[tenor]) for tenor in sorted(by_tenor)]


def interpolate_curve_rate(curve: Sequence[CurveItem] | Sequence[CurvePoint], tenor_years: float) -> float:
    points = _ensure_curve_points(curve)
    tenor = max(0.0, float(tenor_years))

    if tenor <= points[0].tenor_years:
        return points[0].rate
    if tenor >= points[-1].tenor_years:
        return points[-1].rate

    for left, right in zip(points, points[1:]):
        if left.tenor_years <= tenor <= right.tenor_years:
            width = right.tenor_years - left.tenor_years
            if width == 0:
                return right.rate
            weight = (tenor - left.tenor_years) / width
            return left.rate + weight * (right.rate - left.rate)

    return points[-1].rate


def add_months(source: date, months: int) -> date:
    month_index = source.month - 1 + months
    year = source.year + month_index // 12
    month = month_index % 12 + 1
    day = min(source.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def year_fraction(start: date, end: date, day_count: str = "ACT/365") -> float:
    if day_count.upper() != "ACT/365":
        raise ValueError("Only ACT/365 day count is supported in this version.")
    return (end - start).days / 365.0


def build_bond_cashflows(issue: BondIssue | Mapping[str, Any]) -> list[dict[str, Any]]:
    bond = issue if isinstance(issue, BondIssue) else BondIssue.from_mapping(issue)
    bond.validate()

    rows: list[BondCashflow] = []
    period_start = bond.issue_date
    while period_start < bond.maturity_date:
        scheduled_end = add_months(period_start, bond.payment_frequency_months)
        period_end = min(scheduled_end, bond.maturity_date)
        accrual = year_fraction(period_start, period_end, bond.day_count)
        coupon = bond.notional * bond.coupon_rate * accrual
        principal = bond.notional if period_end == bond.maturity_date else 0.0
        rows.append(
            BondCashflow(
                period_start=period_start,
                period_end=period_end,
                payment_date=period_end,
                accrual_years=accrual,
                coupon_cashflow=coupon,
                principal_cashflow=principal,
            )
        )
        period_start = period_end

    return [row.as_dict() for row in rows]


def value_bond_cashflows(
    cashflows: Sequence[Mapping[str, Any]],
    discount_curve: Sequence[CurveItem] | Sequence[CurvePoint],
    valuation_date: DateLike,
    *,
    include_coupon: bool = True,
    include_principal: bool = True,
) -> dict[str, Any]:
    value_date = parse_date(valuation_date)
    curve_points = _ensure_curve_points(discount_curve)
    rows: list[dict[str, Any]] = []
    total_pv = 0.0

    for row in cashflows:
        payment_date = parse_date(row["payment_date"])
        if payment_date <= value_date:
            continue

        amount = 0.0
        if include_coupon:
            amount += float(row["coupon_cashflow"])
        if include_principal:
            amount += float(row["principal_cashflow"])
        if amount == 0.0:
            continue

        tenor = year_fraction(value_date, payment_date)
        discount_rate = interpolate_curve_rate(curve_points, tenor)
        discount_factor = _discount_factor(discount_rate, tenor)
        pv = amount * discount_factor
        total_pv += pv
        rows.append(
            {
                "payment_date": payment_date.isoformat(),
                "tenor_years": tenor,
                "amount": amount,
                "discount_rate": discount_rate,
                "discount_factor": discount_factor,
                "present_value": pv,
            }
        )

    return {"total_pv": total_pv, "rows": rows}


def value_floating_swap_leg(
    cashflows: Sequence[Mapping[str, Any]],
    projection_curve: Sequence[CurveItem] | Sequence[CurvePoint],
    discount_curve: Sequence[CurveItem] | Sequence[CurvePoint],
    valuation_date: DateLike,
    *,
    notional: float,
    spread_bps: float,
    hedge_ratio: float = 1.0,
    pay_receive: str = "pay",
) -> dict[str, Any]:
    sign = _pay_receive_sign(pay_receive)
    value_date = parse_date(valuation_date)
    projection_points = _ensure_curve_points(projection_curve)
    discount_points = _ensure_curve_points(discount_curve)
    spread_decimal = float(spread_bps) / 10000.0

    rows: list[dict[str, Any]] = []
    total_pv = 0.0
    for row in cashflows:
        payment_date = parse_date(row["payment_date"])
        if payment_date <= value_date:
            continue

        tenor = year_fraction(value_date, payment_date)
        projected_base_rate = interpolate_curve_rate(projection_points, tenor)
        floating_rate = projected_base_rate + spread_decimal
        amount = sign * float(notional) * float(hedge_ratio) * floating_rate * float(row["accrual_years"])
        discount_rate = interpolate_curve_rate(discount_points, tenor)
        discount_factor = _discount_factor(discount_rate, tenor)
        pv = amount * discount_factor
        total_pv += pv
        rows.append(
            {
                "payment_date": payment_date.isoformat(),
                "tenor_years": tenor,
                "accrual_years": float(row["accrual_years"]),
                "projected_base_rate": projected_base_rate,
                "spread_bps": float(spread_bps),
                "floating_rate": floating_rate,
                "amount": amount,
                "discount_rate": discount_rate,
                "discount_factor": discount_factor,
                "present_value": pv,
            }
        )

    return {"total_pv": total_pv, "rows": rows}


def solve_swap_spread_bps(
    cashflows: Sequence[Mapping[str, Any]],
    projection_curve: Sequence[CurveItem] | Sequence[CurvePoint],
    discount_curve: Sequence[CurveItem] | Sequence[CurvePoint],
    valuation_date: DateLike,
    *,
    target_pv: float,
    notional: float,
    hedge_ratio: float = 1.0,
    pay_receive: str = "pay",
    target_net_pv: float = 0.0,
) -> dict[str, Any]:
    if hedge_ratio <= 0:
        raise ValueError("hedge_ratio must be positive.")

    sign = _pay_receive_sign(pay_receive)
    value_date = parse_date(valuation_date)
    projection_points = _ensure_curve_points(projection_curve)
    discount_points = _ensure_curve_points(discount_curve)

    base_pv = 0.0
    annuity = 0.0
    for row in cashflows:
        payment_date = parse_date(row["payment_date"])
        if payment_date <= value_date:
            continue

        tenor = year_fraction(value_date, payment_date)
        projected_base_rate = interpolate_curve_rate(projection_points, tenor)
        discount_rate = interpolate_curve_rate(discount_points, tenor)
        discount_factor = _discount_factor(discount_rate, tenor)
        accrual_notional = float(notional) * float(hedge_ratio) * float(row["accrual_years"])
        annuity += accrual_notional * discount_factor
        base_pv += sign * accrual_notional * projected_base_rate * discount_factor

    pv_per_bp = sign * annuity / 10000.0
    if abs(pv_per_bp) < 1e-12:
        raise ValueError("Cannot solve spread: no future swap cashflows.")

    spread_bps = (float(target_net_pv) - float(target_pv) - base_pv) / pv_per_bp
    swap_leg = value_floating_swap_leg(
        cashflows,
        projection_points,
        discount_points,
        value_date,
        notional=notional,
        spread_bps=spread_bps,
        hedge_ratio=hedge_ratio,
        pay_receive=pay_receive,
    )
    net_pv = float(target_pv) + float(swap_leg["total_pv"])

    return {
        "fair_spread_bps": spread_bps,
        "base_float_leg_pv_without_spread": base_pv,
        "pv_change_per_1bp": pv_per_bp,
        "target_pv": float(target_pv),
        "swap_pv": float(swap_leg["total_pv"]),
        "net_pv": net_pv,
        "target_net_pv": float(target_net_pv),
        "swap_cashflows": swap_leg["rows"],
    }


def evaluate_bond_swap_package(
    issue: BondIssue | Mapping[str, Any],
    curve: Sequence[CurveItem] | Sequence[CurvePoint],
    *,
    valuation_date: DateLike | None = None,
    rate_scenarios_1y: Sequence[Any] | None = None,
    hedge_ratios: Sequence[float] = (1.0, 0.75, 0.5),
    include_full_issue_variant: bool = True,
) -> dict[str, Any]:
    bond = issue if isinstance(issue, BondIssue) else BondIssue.from_mapping(issue)
    bond.validate()
    value_date = parse_date(valuation_date) if valuation_date is not None else bond.issue_date
    if value_date >= bond.maturity_date:
        raise ValueError("valuation_date must be earlier than maturity_date.")

    curve_points = _ensure_curve_points(curve)
    cashflows = build_bond_cashflows(bond)
    coupon_pv = value_bond_cashflows(
        cashflows, curve_points, value_date, include_coupon=True, include_principal=False
    )
    principal_pv = value_bond_cashflows(
        cashflows, curve_points, value_date, include_coupon=False, include_principal=True
    )
    full_pv = value_bond_cashflows(
        cashflows, curve_points, value_date, include_coupon=True, include_principal=True
    )

    scenarios = _normalize_rate_scenarios(rate_scenarios_1y, curve_points)
    construction_specs: list[dict[str, Any]] = []
    for hedge_ratio in hedge_ratios:
        ratio = float(hedge_ratio)
        if ratio <= 0:
            raise ValueError("hedge_ratios must contain only positive values.")
        construction_specs.append(
            {
                "name": f"coupon_hedge_{int(round(ratio * 100))}pct",
                "description": "Floating swap leg offsets coupon cashflows only.",
                "target_type": "coupon_only",
                "hedge_ratio": ratio,
                "target_pv": float(coupon_pv["total_pv"]) * ratio,
            }
        )

    if include_full_issue_variant:
        construction_specs.append(
            {
                "name": "full_issue_hedge_100pct",
                "description": "Floating leg offsets coupon plus principal PV.",
                "target_type": "coupon_plus_principal",
                "hedge_ratio": 1.0,
                "target_pv": float(full_pv["total_pv"]),
            }
        )

    constructions = [
        _evaluate_construction(
            spec,
            bond,
            cashflows,
            curve_points,
            value_date,
            scenarios,
        )
        for spec in construction_specs
    ]

    return {
        "issue": bond.as_dict(),
        "valuation_date": value_date.isoformat(),
        "curve": [point.as_dict() for point in curve_points],
        "cashflows": cashflows,
        "bond_pv": {
            "coupon_only": float(coupon_pv["total_pv"]),
            "principal_only": float(principal_pv["total_pv"]),
            "coupon_plus_principal": float(full_pv["total_pv"]),
        },
        "constructions": constructions,
        "model_notes": [
            "Scenario curves are built by shifting the curve around the 1Y pivot rate.",
            "ACT/365 and annual compounding are used in this educational model.",
        ],
        "warnings": _build_warnings(constructions),
    }


def _evaluate_construction(
    spec: Mapping[str, Any],
    bond: BondIssue,
    cashflows: Sequence[Mapping[str, Any]],
    curve_points: Sequence[CurvePoint],
    value_date: date,
    scenarios: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    solved = solve_swap_spread_bps(
        cashflows,
        curve_points,
        curve_points,
        value_date,
        target_pv=float(spec["target_pv"]),
        notional=bond.notional,
        hedge_ratio=float(spec["hedge_ratio"]),
        pay_receive="pay",
    )
    spread = float(solved["fair_spread_bps"])
    scenario_date = min(add_months(value_date, 12), bond.maturity_date)
    base_remaining = _remaining_net_pv_for_construction(
        spec,
        bond,
        cashflows,
        curve_points,
        curve_points,
        scenario_date,
        spread,
    )

    scenario_rows = []
    for scenario in scenarios:
        shifted_curve = shift_curve_to_1y_rate(curve_points, float(scenario["rate_1y"]))
        scenario_result = _remaining_net_pv_for_construction(
            spec,
            bond,
            cashflows,
            shifted_curve,
            shifted_curve,
            scenario_date,
            spread,
        )
        scenario_rows.append(
            {
                "name": scenario["name"],
                "scenario_date": scenario_date.isoformat(),
                "rate_1y": float(scenario["rate_1y"]),
                "shift_vs_base_1y_bps": float(scenario["shift_vs_base_1y_bps"]),
                "remaining_target_pv": scenario_result["remaining_target_pv"],
                "remaining_swap_pv": scenario_result["remaining_swap_pv"],
                "net_pv": scenario_result["net_pv"],
                "delta_vs_base_remaining_pv": scenario_result["net_pv"] - base_remaining["net_pv"],
            }
        )

    return {
        "name": spec["name"],
        "description": spec["description"],
        "target_type": spec["target_type"],
        "hedge_ratio": float(spec["hedge_ratio"]),
        "fair_spread_bps": spread,
        "target_pv": float(solved["target_pv"]),
        "swap_pv": float(solved["swap_pv"]),
        "net_pv": float(solved["net_pv"]),
        "pv_change_per_1bp": float(solved["pv_change_per_1bp"]),
        "scenario_date": scenario_date.isoformat(),
        "scenarios": scenario_rows,
    }


def shift_curve_to_1y_rate(
    curve: Sequence[CurveItem] | Sequence[CurvePoint],
    rate_1y: float,
    *,
    pivot_tenor_years: float = 1.0,
) -> list[CurvePoint]:
    points = _ensure_curve_points(curve)
    scenario_rate = parse_rate(rate_1y)
    base_pivot_rate = interpolate_curve_rate(points, pivot_tenor_years)
    delta = scenario_rate - base_pivot_rate
    shifted: dict[float, float] = {}

    for point in points:
        if point.tenor_years <= 0:
            weight = 0.0
        elif point.tenor_years < pivot_tenor_years:
            weight = point.tenor_years / pivot_tenor_years
        else:
            weight = 1.0
        shifted[point.tenor_years] = point.rate + delta * weight

    shifted[pivot_tenor_years] = scenario_rate
    return [CurvePoint(tenor, shifted[tenor]) for tenor in sorted(shifted)]


def _remaining_net_pv_for_construction(
    spec: Mapping[str, Any],
    bond: BondIssue,
    cashflows: Sequence[Mapping[str, Any]],
    projection_curve: Sequence[CurvePoint],
    discount_curve: Sequence[CurvePoint],
    valuation_date: date,
    spread_bps: float,
) -> dict[str, float]:
    include_principal = spec["target_type"] == "coupon_plus_principal"
    target = value_bond_cashflows(
        cashflows,
        discount_curve,
        valuation_date,
        include_coupon=True,
        include_principal=include_principal,
    )
    target_pv = float(target["total_pv"]) * float(spec["hedge_ratio"])
    swap = value_floating_swap_leg(
        cashflows,
        projection_curve,
        discount_curve,
        valuation_date,
        notional=bond.notional,
        spread_bps=spread_bps,
        hedge_ratio=float(spec["hedge_ratio"]),
        pay_receive="pay",
    )
    swap_pv = float(swap["total_pv"])
    return {
        "remaining_target_pv": target_pv,
        "remaining_swap_pv": swap_pv,
        "net_pv": target_pv + swap_pv,
    }


def _normalize_rate_scenarios(
    raw_scenarios: Sequence[Any] | None,
    curve_points: Sequence[CurvePoint],
) -> list[dict[str, Any]]:
    base_rate_1y = interpolate_curve_rate(curve_points, 1.0)
    if raw_scenarios is None:
        raw_scenarios = [
            {"name": "rates_down_200bp", "rate_1y": base_rate_1y - 0.02},
            {"name": "rates_down_100bp", "rate_1y": base_rate_1y - 0.01},
            {"name": "base_curve", "rate_1y": base_rate_1y},
            {"name": "rates_up_100bp", "rate_1y": base_rate_1y + 0.01},
            {"name": "rates_up_200bp", "rate_1y": base_rate_1y + 0.02},
        ]

    scenarios: list[dict[str, Any]] = []
    for index, item in enumerate(raw_scenarios, start=1):
        if isinstance(item, Mapping):
            rate = parse_rate(item["rate_1y"])
            name = str(item.get("name", f"scenario_{index}"))
        else:
            rate = parse_rate(item)
            name = f"rate_1y_{rate:.4f}"
        scenarios.append(
            {
                "name": name,
                "rate_1y": rate,
                "shift_vs_base_1y_bps": (rate - base_rate_1y) * 10000.0,
            }
        )
    return scenarios


def _build_warnings(constructions: Sequence[Mapping[str, Any]]) -> list[str]:
    warnings: list[str] = []
    for construction in constructions:
        spread = abs(float(construction["fair_spread_bps"]))
        if spread > 1000:
            warnings.append(
                f"{construction['name']}: fair spread is above 1000 bps; check whether principal should be included in the hedge target."
            )
    return warnings


def _discount_factor(rate: float, tenor_years: float) -> float:
    tenor = max(0.0, float(tenor_years))
    if tenor == 0:
        return 1.0
    if rate <= -0.999999:
        raise ValueError("Discount rate is too close to -100%.")
    return 1.0 / ((1.0 + float(rate)) ** tenor)


def _ensure_curve_points(curve: Sequence[CurveItem] | Sequence[CurvePoint]) -> list[CurvePoint]:
    if not curve:
        raise ValueError("curve must contain at least one point.")
    first = curve[0]
    if isinstance(first, CurvePoint):
        return sorted(curve, key=lambda point: point.tenor_years)  # type: ignore[arg-type]
    return normalize_curve_points(curve)  # type: ignore[arg-type]


def _pay_receive_sign(pay_receive: str) -> float:
    mode = pay_receive.strip().lower()
    if mode == "pay":
        return -1.0
    if mode == "receive":
        return 1.0
    raise ValueError("pay_receive must be 'pay' or 'receive'.")


def _positive_float(raw: Any, label: str) -> float:
    value = float(raw)
    if value <= 0:
        raise ValueError(f"{label} must be positive.")
    return value
