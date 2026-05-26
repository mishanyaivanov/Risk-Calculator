from __future__ import annotations

from io import BytesIO
from typing import Any

import pandas as pd


PRICE_COLUMN_CANDIDATES = [
    "price",
    "close",
    "last",
    "value",
    "px_last",
    "adj_close",
]

DATE_COLUMN_CANDIDATES = [
    "date",
    "datetime",
    "time",
]

TICKER_COLUMN_CANDIDATES = [
    "ticker",
    "symbol",
    "asset",
    "instrument",
    "secid",
]

WEIGHT_COLUMN_CANDIDATES = [
    "weight",
    "share",
    "allocation",
    "portion",
]

FIGI_COLUMN_CANDIDATES = [
    "figi",
]


def _normalize_column_name(column_name: Any) -> str:
    return str(column_name).strip().lower().replace(" ", "_")


def _read_table_from_upload(file_bytes: bytes, filename: str) -> pd.DataFrame:
    lower_name = (filename or "").lower()
    buffer = BytesIO(file_bytes)

    if lower_name.endswith(".csv"):
        return pd.read_csv(buffer)
    if lower_name.endswith(".xlsx") or lower_name.endswith(".xls"):
        return pd.read_excel(buffer)

    try:
        buffer.seek(0)
        return pd.read_excel(buffer)
    except Exception:
        buffer.seek(0)
        return pd.read_csv(buffer)


def _find_column(columns: list[str], candidates: list[str]) -> str | None:
    for candidate in candidates:
        if candidate in columns:
            return candidate
    return None


def parse_price_series_file(file_bytes: bytes, filename: str) -> dict[str, Any]:
    dataframe = _read_table_from_upload(file_bytes, filename).copy()
    if dataframe.empty:
        raise ValueError("The uploaded file is empty.")

    dataframe.columns = [_normalize_column_name(column) for column in dataframe.columns]
    columns = list(dataframe.columns)

    price_column = _find_column(columns, PRICE_COLUMN_CANDIDATES)
    date_column = _find_column(columns, DATE_COLUMN_CANDIDATES)

    if price_column is None:
        if len(columns) == 1:
            price_column = columns[0]
        elif len(columns) >= 2:
            price_column = columns[1]
            date_column = columns[0]
        else:
            raise ValueError("Could not detect a price column in the uploaded file.")

    price_series = pd.to_numeric(dataframe[price_column], errors="coerce").dropna()
    prices = [float(value) for value in price_series.tolist()]
    if len(prices) < 2:
        raise ValueError("The file must contain at least 2 numeric price observations.")

    preview_rows = []
    preview_frame = dataframe.head(5).copy()
    preview_frame = preview_frame.where(pd.notnull(preview_frame), None)
    for _, row in preview_frame.iterrows():
        preview_rows.append({key: row[key] for key in preview_frame.columns})

    return {
        "kind": "price_series",
        "filename": filename,
        "detected_price_column": price_column,
        "detected_date_column": date_column,
        "observations": len(prices),
        "prices": prices,
        "manual_prices_text": " ".join(str(price) for price in prices),
        "preview_rows": preview_rows,
    }


def parse_portfolio_file(file_bytes: bytes, filename: str) -> dict[str, Any]:
    dataframe = _read_table_from_upload(file_bytes, filename).copy()
    if dataframe.empty:
        raise ValueError("The uploaded file is empty.")

    dataframe.columns = [_normalize_column_name(column) for column in dataframe.columns]
    columns = list(dataframe.columns)

    ticker_column = _find_column(columns, TICKER_COLUMN_CANDIDATES)
    figi_column = _find_column(columns, FIGI_COLUMN_CANDIDATES)
    weight_column = _find_column(columns, WEIGHT_COLUMN_CANDIDATES)

    if ticker_column is None and figi_column is None:
        raise ValueError("The file must contain a ticker-like column or a FIGI column.")
    if weight_column is None:
        raise ValueError("The file must contain a weight column.")

    rows = []
    unresolved_rows = 0
    for _, row in dataframe.iterrows():
        ticker = ""
        if ticker_column is not None and pd.notnull(row[ticker_column]):
            ticker = str(row[ticker_column]).strip()

        figi = ""
        if figi_column is not None and pd.notnull(row[figi_column]):
            figi = str(row[figi_column]).strip()

        weight_raw = pd.to_numeric(pd.Series([row[weight_column]]), errors="coerce").iloc[0]
        if pd.isna(weight_raw):
            continue

        weight = float(weight_raw)
        if abs(weight) > 1.0:
            weight /= 100.0

        if not ticker and not figi:
            unresolved_rows += 1
            continue

        rows.append(
            {
                "ticker": ticker,
                "figi": figi,
                "weight": weight,
            }
        )

    if not rows:
        raise ValueError("No valid portfolio rows were found in the file.")

    preview_rows = []
    preview_frame = dataframe.head(5).copy()
    preview_frame = preview_frame.where(pd.notnull(preview_frame), None)
    for _, row in preview_frame.iterrows():
        preview_rows.append({key: row[key] for key in preview_frame.columns})

    return {
        "kind": "portfolio",
        "filename": filename,
        "detected_ticker_column": ticker_column,
        "detected_figi_column": figi_column,
        "detected_weight_column": weight_column,
        "rows": rows,
        "row_count": len(rows),
        "unresolved_rows": unresolved_rows,
        "preview_rows": preview_rows,
    }
