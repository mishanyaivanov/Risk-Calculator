from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import os

try:
    from t_tech.invest import Client, CandleInterval
    from t_tech.invest.services import InstrumentsService
    TINKOFF_AVAILABLE = True
except ImportError:
    try:
        from tinkoff.invest import Client, CandleInterval
        from tinkoff.invest.services import InstrumentsService
        TINKOFF_AVAILABLE = True
    except ImportError:
        TINKOFF_AVAILABLE = False
        Client = None
        CandleInterval = None
        InstrumentsService = None


TOKEN = os.getenv("TINKOFF_TOKEN", "Token")
CACHE_PATH = Path(__file__).resolve().parent.parent / "cache" / "tinkoff_instruments_cache.json"
INSTRUMENT_METHODS = ("shares", "bonds", "etfs", "currencies")


def search_rank(query: str, ticker: str, name: str, instrument_type: str) -> tuple:
    query_lower = query.strip().lower()
    ticker_lower = (ticker or "").strip().lower()
    name_lower = (name or "").strip().lower()

    if ticker_lower == query_lower:
        bucket = 0
    elif ticker_lower.startswith(query_lower):
        bucket = 1
    elif name_lower == query_lower:
        bucket = 2
    elif query_lower in ticker_lower:
        bucket = 3
    elif query_lower in name_lower:
        bucket = 4
    else:
        bucket = 5

    type_priority = {
        "shares": 0,
        "bonds": 1,
        "etfs": 2,
        "currencies": 3,
    }.get(instrument_type, 9)

    return (
        bucket,
        type_priority,
        abs(len(ticker_lower) - len(query_lower)),
        abs(len(name_lower) - len(query_lower)),
        ticker_lower,
        name_lower,
    )


def similarity_score(str1: str, str2: str, threshold: float) -> bool:
    len_str1 = len(str1)
    len_str2 = len(str2)
    str1 = str1.lower()
    str2 = str2.lower()
    dp = [[0] * (len_str2 + 1) for _ in range(len_str1 + 1)]
    for i in range(len_str1 + 1):
        dp[i][0] = i
    for j in range(len_str2 + 1):
        dp[0][j] = j
    for i in range(1, len_str1 + 1):
        for j in range(1, len_str2 + 1):
            cost = 0 if str1[i - 1] == str2[j - 1] else 1
            dp[i][j] = min(
                dp[i - 1][j] + 1,
                dp[i][j - 1] + 1,
                dp[i - 1][j - 1] + cost,
            )
    return dp[len_str1][len_str2] <= threshold


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe_token(token: Optional[str]) -> str:
    return token or TOKEN


def _cache_shell(items: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    return {
        "updated_at": None,
        "item_count": 0,
        "items": items or [],
    }


def load_instrument_cache(cache_path: Path = CACHE_PATH) -> Dict[str, Any]:
    if not cache_path.exists():
        return _cache_shell()
    try:
        with cache_path.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)
        items = payload.get("items", [])
        if not isinstance(items, list):
            return _cache_shell()
        return {
            "updated_at": payload.get("updated_at"),
            "item_count": int(payload.get("item_count", len(items))),
            "items": items,
        }
    except Exception:
        return _cache_shell()


def _write_instrument_cache(items: List[Dict[str, Any]], cache_path: Path = CACHE_PATH) -> Dict[str, Any]:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": _now_iso(),
        "item_count": len(items),
        "items": items,
    }
    with cache_path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    return payload


def _fetch_all_instruments_live(token: str) -> List[Dict[str, Any]]:
    if not TINKOFF_AVAILABLE:
        return []
    if token == "Token":
        return []

    results: List[Dict[str, Any]] = []
    seen_figis: set[str] = set()
    with Client(token) as cl:
        instruments: InstrumentsService = cl.instruments
        for method_name in INSTRUMENT_METHODS:
            method = getattr(instruments, method_name)
            for item in method().instruments:
                figi = str(getattr(item, "figi", "") or "").strip()
                if not figi or figi in seen_figis:
                    continue
                seen_figis.add(figi)
                results.append(
                    {
                        "ticker": str(getattr(item, "ticker", "") or "").strip(),
                        "figi": figi,
                        "name": str(getattr(item, "name", "") or "").strip(),
                        "type": method_name,
                    }
                )
    results.sort(key=lambda item: ((item.get("ticker") or "").lower(), (item.get("name") or "").lower()))
    return results


def rebuild_instrument_cache(token: str = TOKEN, cache_path: Path = CACHE_PATH) -> Dict[str, Any]:
    items = _fetch_all_instruments_live(_safe_token(token))
    return _write_instrument_cache(items, cache_path)


def merge_cached_instruments(items: List[Dict[str, Any]], cache_path: Path = CACHE_PATH) -> Dict[str, Any]:
    current = load_instrument_cache(cache_path)
    by_figi: Dict[str, Dict[str, Any]] = {
        str(item.get("figi") or ""): item for item in current.get("items", []) if str(item.get("figi") or "")
    }
    for item in items:
        figi = str(item.get("figi") or "")
        if not figi:
            continue
        by_figi[figi] = {
            "ticker": str(item.get("ticker", "") or "").strip(),
            "figi": figi,
            "name": str(item.get("name", "") or "").strip(),
            "type": str(item.get("type", "") or "").strip(),
        }
    merged = sorted(by_figi.values(), key=lambda item: ((item.get("ticker") or "").lower(), (item.get("name") or "").lower()))
    return _write_instrument_cache(merged, cache_path)


def search_instrument_cache(query: str, limit: int = 30, cache_path: Path = CACHE_PATH) -> List[Dict[str, Any]]:
    query = (query or "").strip()
    if not query:
        return []
    payload = load_instrument_cache(cache_path)
    items = payload.get("items", [])
    if not items:
        return []

    results: List[Dict[str, Any]] = []
    query_lower = query.lower()
    for item in items:
        ticker = str(item.get("ticker", "") or "")
        name = str(item.get("name", "") or "")
        ticker_lower = ticker.lower()
        name_lower = name.lower()

        matched = (
            ticker_lower == query_lower
            or ticker_lower.startswith(query_lower)
            or name_lower.startswith(query_lower)
            or query_lower in ticker_lower
            or query_lower in name_lower
        )

        if not matched and len(query_lower) >= 3:
            thresh_name = min(len(query_lower), len(name_lower)) / 1.75 if name_lower else 0
            thresh_ticker = min(len(query_lower), len(ticker_lower)) / 1.75 if ticker_lower else 0
            matched = (
                (thresh_name > 0 and similarity_score(query_lower, name_lower, thresh_name))
                or (thresh_ticker > 0 and similarity_score(query_lower, ticker_lower, thresh_ticker))
            )

        if matched:
            results.append(item)

    results.sort(key=lambda item: search_rank(query, item.get("ticker", ""), item.get("name", ""), item.get("type", "")))
    return results[:limit]


def find_instruments_live(name: str, token: str = TOKEN) -> List[Dict]:
    if not TINKOFF_AVAILABLE:
        return [{"name": "Tinkoff Library Missing", "ticker": "ERROR", "figi": "", "type": "error"}]
    if _safe_token(token) == "Token":
        return []

    results: List[Dict[str, Any]] = []
    seen_figis: set[str] = set()
    try:
        with Client(_safe_token(token)) as cl:
            instruments: InstrumentsService = cl.instruments
            for method_name in INSTRUMENT_METHODS:
                method = getattr(instruments, method_name)
                for item in method().instruments:
                    thresh_name = min(len(name), len(item.name)) / 1.75
                    thresh_ticker = min(len(name), len(item.ticker)) / 1.75
                    if similarity_score(name, item.name, thresh_name) or similarity_score(name, item.ticker, thresh_ticker):
                        if item.figi in seen_figis:
                            continue
                        seen_figis.add(item.figi)
                        results.append(
                            {
                                "ticker": item.ticker,
                                "figi": item.figi,
                                "name": item.name,
                                "type": method_name,
                            }
                        )
    except Exception as exc:
        print(f"Error finding instruments: {exc}")
        return []
    results.sort(key=lambda item: search_rank(name, item.get("ticker", ""), item.get("name", ""), item.get("type", "")))
    return results


def find_instruments(name: str, token: str = TOKEN) -> List[Dict]:
    return search_instrument_cache(name)


def get_cache_status(cache_path: Path = CACHE_PATH) -> Dict[str, Any]:
    payload = load_instrument_cache(cache_path)
    return {
        "updated_at": payload.get("updated_at"),
        "item_count": payload.get("item_count", 0),
        "path": str(cache_path),
    }


def _price_to_float(price) -> float:
    return price.units + price.nano / 10 ** 9


def get_candles(figi: str, start_date: str, end_date: str, token: str = TOKEN) -> List[Dict]:
    if not TINKOFF_AVAILABLE:
        return []
    token = _safe_token(token)
    if token == "Token":
        return []

    data = []
    try:
        with Client(token) as cl:
            for candle in cl.get_all_candles(
                figi=figi,
                from_=datetime.strptime(start_date, "%Y-%m-%d"),
                to=datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1),
                interval=CandleInterval.CANDLE_INTERVAL_DAY,
            ):
                data.append(
                    {
                        "date": str(candle.time + timedelta(hours=3))[:19],
                        "open": _price_to_float(candle.open),
                        "high": _price_to_float(candle.high),
                        "low": _price_to_float(candle.low),
                        "close": _price_to_float(candle.close),
                        "volume": candle.volume,
                    }
                )
    except Exception as exc:
        print(f"Error fetching candles: {exc}")
        return []
    return data
