from typing import Any, Dict, List, Optional

import aiomoex


ISS_BASE_URL = "https://iss.moex.com/iss"


def _rows_to_dicts(payload: Dict[str, Any], table_name: str) -> List[Dict[str, Any]]:
    table = payload.get(table_name, {})
    columns = table.get("columns", [])
    rows = table.get("data", [])
    return [dict(zip(columns, row)) for row in rows]


async def _get_iss_json(session, url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    query = {"iss.meta": "off"}
    if params:
        query.update(params)

    async with session.get(url, params=query) as response:
        response.raise_for_status()
        return await response.json()


async def _resolve_security_board(session, secid: str) -> Dict[str, Any]:
    payload = await _get_iss_json(session, f"{ISS_BASE_URL}/securities/{secid}.json")
    boards = _rows_to_dicts(payload, "boards")
    if not boards:
        raise ValueError(f"MOEX security '{secid}' was not found.")

    preferred_boards = [board for board in boards if board.get("is_primary") == 1]
    if not preferred_boards:
        preferred_boards = [board for board in boards if board.get("is_traded") == 1]
    if not preferred_boards:
        preferred_boards = boards

    return preferred_boards[0]


async def get_market_instruments(session, engine: str, market: str) -> List[Dict[str, Any]]:
    payload = await _get_iss_json(
        session,
        f"{ISS_BASE_URL}/engines/{engine}/markets/{market}/securities.json",
        params={
            "iss.only": "securities",
            "securities.columns": "SECID,SHORTNAME,LOTSIZE,MINSTEP,PREVPRICE,ASSETCODE",
        },
    )
    return _rows_to_dicts(payload, "securities")


async def get_option_board(session, underlying_asset_code: str) -> List[Dict[str, Any]]:
    payload = await _get_iss_json(
        session,
        f"{ISS_BASE_URL}/engines/futures/markets/options/securities.json",
        params={
            "securities.columns": (
                "SECID,BOARDID,SHORTNAME,ASSETCODE,OPTIONTYPE,STRIKE,"
                "LASTTRADEDATE,PREVSETTLEPRICE,UNDERLYINGASSET,UNDERLYINGSETTLEPRICE,"
                "SETTLEPRICE_CLR"
            ),
            "marketdata.columns": "SECID,BID,OFFER,LAST,OPENPOSITION,NUMTRADES,VOLTODAY,UPDATETIME",
        },
    )

    underlying = underlying_asset_code.upper()
    securities_rows = _rows_to_dicts(payload, "securities")
    marketdata_rows = _rows_to_dicts(payload, "marketdata")
    marketdata_by_secid = {
        row["SECID"]: row for row in marketdata_rows if row.get("SECID")
    }

    merged_rows: List[Dict[str, Any]] = []
    for row in securities_rows:
        if str(row.get("ASSETCODE", "")).upper() != underlying:
            continue

        market_row = marketdata_by_secid.get(row["SECID"], {})
        merged_rows.append(
            {
                "SECID": row.get("SECID"),
                "BOARDID": row.get("BOARDID"),
                "SHORTNAME": row.get("SHORTNAME"),
                "ASSETCODE": row.get("ASSETCODE"),
                "OPTION_TYPE": row.get("OPTIONTYPE"),
                "STRIKE": row.get("STRIKE"),
                "EXP_DATE": row.get("LASTTRADEDATE"),
                "UNDERLYING_ASSET": row.get("UNDERLYINGASSET"),
                "UNDERLYING_PRICE": row.get("UNDERLYINGSETTLEPRICE"),
                "PREVSETTLEPRICE": row.get("PREVSETTLEPRICE"),
                "SETTLEPRICE_CLR": row.get("SETTLEPRICE_CLR"),
                "BID": market_row.get("BID"),
                "ASK": market_row.get("OFFER"),
                "LAST_PRICE": market_row.get("LAST"),
                "OPENPOSITION": market_row.get("OPENPOSITION"),
                "NUMTRADES": market_row.get("NUMTRADES"),
                "VOLTODAY": market_row.get("VOLTODAY"),
                "UPDATETIME": market_row.get("UPDATETIME"),
            }
        )

    merged_rows.sort(
        key=lambda row: (
            row.get("EXP_DATE") or "",
            row.get("OPTION_TYPE") or "",
            float(row.get("STRIKE") or 0.0),
            row.get("SECID") or "",
        )
    )
    return merged_rows


async def get_instrument_candles(
    session,
    secid: str,
    start_date: str,
    end_date: str,
    engine: Optional[str] = None,
    market: Optional[str] = None,
) -> List[Dict[str, Any]]:
    resolved_engine = engine
    resolved_market = market
    if not resolved_engine or not resolved_market:
        board = await _resolve_security_board(session, secid)
        resolved_engine = resolved_engine or str(board["engine"])
        resolved_market = resolved_market or str(board["market"])

    candles = await aiomoex.get_market_candles(
        session,
        security=secid,
        start=start_date,
        end=end_date,
        market=resolved_market,
        engine=resolved_engine,
    )

    return [
        {
            "date": candle.get("begin"),
            "open": candle.get("open"),
            "high": candle.get("high"),
            "low": candle.get("low"),
            "close": candle.get("close"),
            "volume": candle.get("value") if candle.get("value") is not None else candle.get("volume"),
        }
        for candle in candles
    ]
