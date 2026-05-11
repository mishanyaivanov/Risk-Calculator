from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import base64
from io import BytesIO
from pathlib import Path
from typing import Any
from uuid import uuid4


def _load_reportlab():
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except Exception as exc:
        raise RuntimeError(
            "PDF reporting requires reportlab. Rebuild the service with updated requirements and try again."
        ) from exc

    return {
        "colors": colors,
        "A4": A4,
        "ParagraphStyle": ParagraphStyle,
        "getSampleStyleSheet": getSampleStyleSheet,
        "mm": mm,
        "pdfmetrics": pdfmetrics,
        "TTFont": TTFont,
        "Image": Image,
        "Paragraph": Paragraph,
        "SimpleDocTemplate": SimpleDocTemplate,
        "Spacer": Spacer,
        "Table": Table,
        "TableStyle": TableStyle,
    }


def _register_fonts(pdfmetrics, TTFont) -> tuple[str, str]:
    candidates = [
        (Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"), Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")),
        (Path("C:/Windows/Fonts/arial.ttf"), Path("C:/Windows/Fonts/arialbd.ttf")),
    ]
    for normal_path, bold_path in candidates:
        if normal_path.exists() and bold_path.exists():
            pdfmetrics.registerFont(TTFont("RiskSans", str(normal_path)))
            pdfmetrics.registerFont(TTFont("RiskSansBold", str(bold_path)))
            return "RiskSans", "RiskSansBold"
    return "Helvetica", "Helvetica-Bold"


def _fmt_currency(value: Any) -> str:
    try:
        return f"{float(value):,.2f} RUB".replace(",", " ")
    except Exception:
        return "--"


def _fmt_percent(value: Any, multiply_100: bool = False, decimals: int = 2) -> str:
    try:
        number = float(value) * 100.0 if multiply_100 else float(value)
        return f"{number:.{decimals}f}%"
    except Exception:
        return "--"


def _fmt_number(value: Any, decimals: int = 3) -> str:
    try:
        return f"{float(value):.{decimals}f}"
    except Exception:
        return "--"


def _severity_label(value: str) -> str:
    mapping = {"green": "Low risk", "yellow": "Medium risk", "red": "High risk"}
    return mapping.get(str(value or "").lower(), "Risk status")


def _styles(parts: dict[str, Any]) -> dict[str, Any]:
    base = parts["getSampleStyleSheet"]()
    normal_font, bold_font = _register_fonts(parts["pdfmetrics"], parts["TTFont"])
    return {
        "title": parts["ParagraphStyle"](
            "RiskTitle",
            parent=base["Title"],
            fontName=bold_font,
            fontSize=18,
            leading=22,
            textColor=parts["colors"].HexColor("#1f3a52"),
            spaceAfter=8,
        ),
        "subtitle": parts["ParagraphStyle"](
            "RiskSubtitle",
            parent=base["BodyText"],
            fontName=normal_font,
            fontSize=8.5,
            leading=11,
            textColor=parts["colors"].HexColor("#5b6770"),
            spaceAfter=12,
        ),
        "section": parts["ParagraphStyle"](
            "RiskSection",
            parent=base["Heading2"],
            fontName=bold_font,
            fontSize=11,
            leading=13,
            textColor=parts["colors"].HexColor("#1f3a52"),
            spaceBefore=6,
            spaceAfter=6,
        ),
        "body": parts["ParagraphStyle"](
            "RiskBody",
            parent=base["BodyText"],
            fontName=normal_font,
            fontSize=8.8,
            leading=11,
            textColor=parts["colors"].HexColor("#243746"),
        ),
        "small": parts["ParagraphStyle"](
            "RiskSmall",
            parent=base["BodyText"],
            fontName=normal_font,
            fontSize=7.8,
            leading=10,
            textColor=parts["colors"].HexColor("#6b7785"),
        ),
        "th": parts["ParagraphStyle"](
            "RiskTH",
            parent=base["BodyText"],
            fontName=bold_font,
            fontSize=8.2,
            leading=10,
            textColor=parts["colors"].white,
        ),
        "td": parts["ParagraphStyle"](
            "RiskTD",
            parent=base["BodyText"],
            fontName=normal_font,
            fontSize=8.2,
            leading=10,
            textColor=parts["colors"].HexColor("#243746"),
        ),
    }


def _kv_table(parts: dict[str, Any], styles: dict[str, Any], rows: list[tuple[str, str]]):
    data = [
        [parts["Paragraph"]("Field", styles["th"]), parts["Paragraph"]("Value", styles["th"])]
    ] + [
        [parts["Paragraph"](str(label), styles["td"]), parts["Paragraph"](str(value), styles["td"])]
        for label, value in rows
    ]
    table = parts["Table"](data, colWidths=[58 * parts["mm"], 114 * parts["mm"]], hAlign="LEFT")
    table.setStyle(parts["TableStyle"]([
        ("BACKGROUND", (0, 0), (-1, 0), parts["colors"].HexColor("#1f3a52")),
        ("GRID", (0, 0), (-1, -1), 0.35, parts["colors"].HexColor("#d9e2ec")),
        ("BACKGROUND", (0, 1), (-1, -1), parts["colors"].white),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table


def _bullets(parts: dict[str, Any], styles: dict[str, Any], items: list[str]):
    flow = []
    for item in items:
        text = str(item).strip()
        if not text:
            continue
        flow.append(parts["Paragraph"](f"- {text}", styles["body"]))
        flow.append(parts["Spacer"](1, 2))
    return flow


def _image_from_data_url(parts: dict[str, Any], data_url: str, width_mm: float = 170.0):
    if not data_url or "," not in data_url:
        return None
    try:
        _, encoded = data_url.split(",", 1)
        image_bytes = base64.b64decode(encoded)
        buffer = BytesIO(image_bytes)
        image = parts["Image"](buffer)
        max_width = width_mm * parts["mm"]
        aspect = image.imageHeight / image.imageWidth if image.imageWidth else 0.6
        image.drawWidth = max_width
        image.drawHeight = max_width * aspect
        return image
    except Exception:
        return None


def _report_doc():
    parts = _load_reportlab()
    styles = _styles(parts)
    buffer = BytesIO()
    doc = parts["SimpleDocTemplate"](
        buffer,
        pagesize=parts["A4"],
        leftMargin=16 * parts["mm"],
        rightMargin=16 * parts["mm"],
        topMargin=16 * parts["mm"],
        bottomMargin=16 * parts["mm"],
    )
    return parts, styles, buffer, doc


def _single_summary(result: dict[str, Any]) -> list[str]:
    risk_status = result.get("risk_status", {}) or {}
    pvar = float((result.get("parametric_var") or {}).get("var_loss", 0.0))
    es = float((result.get("es") or {}).get("es_loss", 0.0))
    share = float(risk_status.get("loss_share_pct", 0.0))
    lines = [
        f"Risk status: {_severity_label(risk_status.get('severity'))}.",
        f"Estimated one-period VaR is {_fmt_currency(pvar)} and represents {_fmt_percent(share)} of the current position size.",
        f"Expected Shortfall is {_fmt_currency(es)}, which is the average loss across the worst modeled outcomes.",
    ]
    return lines


def _portfolio_summary(calculation: dict[str, Any], result: dict[str, Any]) -> list[str]:
    metrics = result.get("portfolio_metrics", {}) or {}
    pvar = float(metrics.get("var_value", 0.0))
    vol = float(metrics.get("annual_volatility", 0.0))
    ret = float(metrics.get("annual_return", 0.0))
    port_value = float(calculation.get("portfolio_value", 0.0) or 0.0)
    share = (pvar / port_value * 100.0) if port_value > 1e-12 else 0.0
    return [
        f"Estimated portfolio VaR is {_fmt_currency(pvar)}, or {_fmt_percent(share)} of the portfolio value.",
        f"Annualized volatility is {_fmt_percent(vol, multiply_100=True)} and annualized return is {_fmt_percent(ret, multiply_100=True)}.",
        "The correlation block and history charts below help explain concentration and diversification quality.",
    ]


def _single_interpretation_summary(result: dict[str, Any]) -> str:
    risk_status = result.get("risk_status", {}) or {}
    share = float(risk_status.get("loss_share_pct", 0.0))
    if share < 2.0:
        return "The position looks manageable under the selected confidence level."
    if share < 5.0:
        return "The position is still workable, but a bad day can produce a visible loss."
    return "The position carries a material downside and should be reviewed with size or hedge adjustments."


def _portfolio_interpretation_summary(calculation: dict[str, Any], result: dict[str, Any]) -> str:
    metrics = result.get("portfolio_metrics", {}) or {}
    port_value = float(calculation.get("portfolio_value", 0.0) or 0.0)
    pvar = float(metrics.get("var_value", 0.0))
    share = (pvar / port_value * 100.0) if port_value > 1e-12 else 0.0
    if share < 3.0:
        return "The portfolio currently appears broadly diversified for the selected setup."
    if share < 6.0:
        return "The portfolio is usable, but concentration or correlation should be monitored."
    return "The portfolio risk is concentrated enough to justify rebalancing or a hedge review."


def build_single_asset_report(calculation: dict[str, Any], result: dict[str, Any], chart_images: dict[str, str] | None = None) -> bytes:
    parts, styles, buffer, doc = _report_doc()
    mode_map = {"tinkoff": "Tinkoff API", "manual": "Manual prices", "random": "Random sample"}
    risk_status = result.get("risk_status", {}) or {}
    lvar = result.get("lvar", {}) or {}
    chart_images = chart_images or {}
    story: list[Any] = [
        parts["Paragraph"]("Risk Calculator Report", styles["title"]),
        parts["Paragraph"](
            f"Single-asset risk report. Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}.",
            styles["subtitle"],
        ),
        parts["Paragraph"]("Input snapshot", styles["section"]),
        _kv_table(parts, styles, [
            ("Mode", mode_map.get(str(calculation.get("mode", "")).lower(), str(calculation.get("mode", "--")))),
            ("Confidence level", _fmt_percent(calculation.get("confidence", 0.0), multiply_100=True, decimals=1)),
            ("Position size", str(calculation.get("position_size", "--"))),
            ("Spread assumption", _fmt_percent(calculation.get("spread_percent", 0.0), decimals=2)),
            ("Liquidation days", str(calculation.get("liquidation_days", "--"))),
            ("Observations", str(result.get("prices_count", "--"))),
        ]),
        parts["Spacer"](1, 8),
        parts["Paragraph"]("Core metrics", styles["section"]),
        _kv_table(parts, styles, [
            ("Current position value", _fmt_currency(result.get("position_value"))),
            ("Last price", _fmt_currency(result.get("last_price"))),
            ("Parametric VaR", _fmt_currency((result.get("parametric_var") or {}).get("var_loss"))),
            ("Historical VaR", _fmt_currency((result.get("historical_var") or {}).get("var_loss"))),
            ("Expected Shortfall", _fmt_currency((result.get("es") or {}).get("es_loss"))),
            ("Stressed LVaR", _fmt_currency(lvar.get("lvar_stressed"))),
        ]),
        parts["Spacer"](1, 8),
        parts["Paragraph"]("Interpretation", styles["section"]),
        _kv_table(parts, styles, [
            ("Risk status", _severity_label(risk_status.get("severity"))),
            ("Loss share", _fmt_percent(risk_status.get("loss_share_pct"), decimals=2)),
            ("Summary", _single_interpretation_summary(result)),
        ]),
    ]

    story.extend([parts["Spacer"](1, 8), parts["Paragraph"]("Executive summary", styles["section"])])
    story.extend(_bullets(parts, styles, _single_summary(result)))

    price_chart = _image_from_data_url(parts, chart_images.get("price_history", ""))
    if price_chart is not None:
        story.extend([parts["Spacer"](1, 8), parts["Paragraph"]("Price history", styles["section"]), price_chart])

    story.extend([parts["Spacer"](1, 8), parts["Paragraph"]("Methodology and limits", styles["section"])])
    story.extend(_bullets(parts, styles, [
        "VaR and ES are model-based estimates and depend on the selected confidence level and input history.",
        "LVaR adds a liquidity adjustment and should be interpreted as a stressed exit cost estimate.",
        "This report is analytical support material and not an investment recommendation.",
    ]))
    doc.build(story)
    return buffer.getvalue()


def build_portfolio_report(calculation: dict[str, Any], result: dict[str, Any], chart_images: dict[str, str] | None = None) -> bytes:
    parts, styles, buffer, doc = _report_doc()
    metrics = result.get("portfolio_metrics", {}) or {}
    explanation = result.get("portfolio_status", {}) or {}
    corr = result.get("correlation_matrix", {}) or {}
    items = calculation.get("items", []) or []
    chart_images = chart_images or {}
    story: list[Any] = [
        parts["Paragraph"]("Risk Calculator Report", styles["title"]),
        parts["Paragraph"](
            f"Portfolio risk report. Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}.",
            styles["subtitle"],
        ),
        parts["Paragraph"]("Input snapshot", styles["section"]),
        _kv_table(parts, styles, [
            ("Confidence level", _fmt_percent(calculation.get("confidence", 0.0), multiply_100=True, decimals=1)),
            ("Portfolio value", _fmt_currency(calculation.get("portfolio_value"))),
            ("History window", f"{calculation.get('start_date', '--')} to {calculation.get('end_date', '--')}"),
            ("Number of assets", str(len(items))),
        ]),
        parts["Spacer"](1, 8),
        parts["Paragraph"]("Core metrics", styles["section"]),
        _kv_table(parts, styles, [
            ("Portfolio VaR", _fmt_currency(metrics.get("var_value"))),
            ("Annual volatility", _fmt_percent(metrics.get("annual_volatility"), multiply_100=True)),
            ("Annual return", _fmt_percent(metrics.get("annual_return"), multiply_100=True)),
            ("Z-score", _fmt_number(metrics.get("z_score"))),
        ]),
        parts["Spacer"](1, 8),
        parts["Paragraph"]("Portfolio composition", styles["section"]),
        _kv_table(parts, styles, [
            (
                str(item.get("ticker") or item.get("figi") or "Asset"),
                _fmt_percent(item.get("weight"), multiply_100=float(item.get("weight", 0)) <= 1.0),
            )
            for item in items
        ] or [("Assets", "--")]),
        parts["Spacer"](1, 8),
        parts["Paragraph"]("Interpretation", styles["section"]),
        _kv_table(parts, styles, [
            ("Risk status", _severity_label(explanation.get("severity"))),
            ("Summary", _portfolio_interpretation_summary(calculation, result)),
        ]),
    ]

    story.extend([parts["Spacer"](1, 8), parts["Paragraph"]("Executive summary", styles["section"])])
    story.extend(_bullets(parts, styles, _portfolio_summary(calculation, result)))

    labels = list(corr.keys())
    if 1 < len(labels) <= 6:
        story.extend([parts["Spacer"](1, 8), parts["Paragraph"]("Correlation overview", styles["section"]), _kv_table(parts, styles, [
            (label, " | ".join(f"{float(corr[label][col]):.2f}" for col in labels))
            for label in labels
        ])])

    for title, key in [
        ("Efficient frontier", "frontier"),
        ("Cumulative return", "cumulative"),
        ("Correlation matrix", "correlation"),
        ("Portfolio allocation", "allocation"),
    ]:
        image = _image_from_data_url(parts, chart_images.get(key, ""))
        if image is not None:
            story.extend([parts["Spacer"](1, 8), parts["Paragraph"](title, styles["section"]), image])

    story.extend([
        parts["Spacer"](1, 8),
        parts["Paragraph"]("Methodology and limits", styles["section"]),
    ])
    story.extend(_bullets(parts, styles, [
            "The portfolio section uses a variance-covariance approach for current VaR estimation.",
            "Return and volatility metrics are history-dependent and may change materially with the sample window.",
            "This report is analytical support material and not an investment recommendation.",
        ]))
    doc.build(story)
    return buffer.getvalue()


@dataclass
class StoredReport:
    filename: str
    content: bytes
    created_at: datetime


class ReportStore:
    def __init__(self, max_reports: int = 20, ttl_minutes: int = 30):
        self.max_reports = max_reports
        self.ttl = timedelta(minutes=ttl_minutes)
        self._reports: dict[str, StoredReport] = {}

    def _cleanup(self) -> None:
        now = datetime.now()
        expired = [key for key, report in self._reports.items() if now - report.created_at > self.ttl]
        for key in expired:
            self._reports.pop(key, None)
        if len(self._reports) > self.max_reports:
            for key, _ in sorted(self._reports.items(), key=lambda item: item[1].created_at)[: len(self._reports) - self.max_reports]:
                self._reports.pop(key, None)

    def save(self, filename: str, content: bytes) -> str:
        self._cleanup()
        report_id = uuid4().hex
        self._reports[report_id] = StoredReport(filename=filename, content=content, created_at=datetime.now())
        return report_id

    def get(self, report_id: str) -> StoredReport | None:
        self._cleanup()
        return self._reports.get(report_id)
