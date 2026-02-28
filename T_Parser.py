from tinkoff.invest import Client, InstrumentStatus, InstrumentIdType, CandleInterval, RequestError, HistoricCandle
from tinkoff.invest.services import InstrumentsService, Services
import pandas as pd
from datetime import datetime, timedelta
import plotly.graph_objects as pl

# from novosti import RbkNews,LentaNews,AiFNews
TOKEN = 'Token'


def simS(str1, str2, zn):
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
    if dp[len_str1][len_str2] <= zn:
        return 1
    return 0


def naiFi(name):
    global TOKEN
    with Client(TOKEN) as cl:
        instruments: InstrumentsService = cl.instruments
        vr = {
            'ticker': [],
            'figi': [],
            'name': [],
            'type': []
        }
        for tipok in ['shares', 'bonds', 'etfs', 'currencies']:
            for item in getattr(instruments, tipok)().instruments:
                if simS(name, item.name, min(len(name), len(item.name)) // 1.75) or simS(name, item.ticker,
                                                                                         min(len(name),
                                                                                             len(item.ticker)) // 1.75):
                    vr['ticker'].append(item.ticker)
                    vr['figi'].append(item.figi)
                    vr['type'].append(tipok)
                    vr['name'].append(item.name)
        da = pd.DataFrame(vr)
    return da


def perd(s):
    return s.units + s.nano / 10 ** 9


name = input('Name:')
vrFi = naiFi(name)
print(vrFi)
n = int(input('Select suitable:'))
fishka = vrFi.iloc[n]['figi']

na = input("Date of start (YYYY-MM-DD):")
kon = input("Date of end (YYYY-MM-DD):")


def svechkiT(na, kon, figi):
    global TOKEN
    da = {'date': [],
          'Open': [],
          'High': [],
          'Low': [],
          'Close': [],
          'Volume': []
          }
    with Client(TOKEN) as cl:
        for candle in cl.get_all_candles(
                figi=fishka,
                from_=datetime.strptime(na, '%Y-%m-%d'),
                to=datetime.strptime(kon, '%Y-%m-%d') + timedelta(days=1),
                interval=CandleInterval.CANDLE_INTERVAL_DAY
        ):
            da['date'].append(str(candle.time + timedelta(hours=3))[:19])
            da['Open'].append(perd(candle.open))
            da['High'].append(perd(candle.high))
            da['Low'].append(perd(candle.low))
            da['Close'].append(perd(candle.close))
            da['Volume'].append(candle.volume)
    da = pd.DataFrame(da)
    return da


td = svechkiT(na, kon, fishka)
print(td)
# fig = pl.Figure(data=[pl.Candlestick(x=td['date'],
#                        open=td['Open'], high=td['High'],
#                        low=td['Low'], close=td['Close'])])
#
#
#
# fig.update_layout(xaxis_rangeslider_visible=True)
# fig.update_layout(showlegend=False,)
#
# fig.show()