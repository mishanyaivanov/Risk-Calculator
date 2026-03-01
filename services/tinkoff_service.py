from datetime import datetime, timedelta
from typing import List, Dict, Union
import os
import sys

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

def similarity_score(str1: str, str2: str, threshold: float) -> bool:
    """Calculates Levenshtein distance-based similarity."""
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
            dp[i][j] = min(dp[i - 1][j] + 1,
                           dp[i][j - 1] + 1,
                           dp[i - 1][j - 1] + cost)
    return dp[len_str1][len_str2] <= threshold

def find_instruments(name: str, token: str = TOKEN) -> List[Dict]:
    """Finds instruments by name using fuzzy search."""
    if not TINKOFF_AVAILABLE:
        return [{"name": "Tinkoff Library Missing", "ticker": "ERROR", "figi": "", "type": "error"}]

    results = []
    if token == "Token":
        return []

    try:
        with Client(token) as cl:
            instruments: InstrumentsService = cl.instruments
            for method_name in ['shares', 'bonds', 'etfs', 'currencies']:
                method = getattr(instruments, method_name)
                for item in method().instruments:
                    thresh_name = min(len(name), len(item.name)) / 1.75
                    thresh_ticker = min(len(name), len(item.ticker)) / 1.75
                    
                    if similarity_score(name, item.name, thresh_name) or \
                       similarity_score(name, item.ticker, thresh_ticker):
                        results.append({
                            'ticker': item.ticker,
                            'figi': item.figi,
                            'name': item.name,
                            'type': method_name
                        })
    except Exception as e:
        print(f"Error finding instruments: {e}")
        return []
    return results

def _price_to_float(price) -> float:
    """Converts Tinkoff price object to float."""
    return price.units + price.nano / 10 ** 9

def get_candles(figi: str, start_date: str, end_date: str, token: str = TOKEN) -> List[Dict]:
    """Fetches historical candles for a given FIGI."""
    if not TINKOFF_AVAILABLE:
        return []

    data = []
    if token == "Token":
        return []

    try:
        with Client(token) as cl:
            for candle in cl.get_all_candles(
                    figi=figi,
                    from_=datetime.strptime(start_date, '%Y-%m-%d'),
                    to=datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1),
                    interval=CandleInterval.CANDLE_INTERVAL_DAY
            ):
                data.append({
                    'date': str(candle.time + timedelta(hours=3))[:19],
                    'open': _price_to_float(candle.open),
                    'high': _price_to_float(candle.high),
                    'low': _price_to_float(candle.low),
                    'close': _price_to_float(candle.close),
                    'volume': candle.volume
                })
    except Exception as e:
        print(f"Error fetching candles: {e}")
        return []
    return data
