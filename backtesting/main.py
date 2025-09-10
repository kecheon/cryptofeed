import yfinance as yf
from backtesting import Backtest
from dmi import DMIStrategy
import pandas as pd
from backtesting.lib import FractionalBacktest


# BTCUSD 1시간봉 예시
data = yf.download("BTC-USD", start="2025-09-01", end="2025-09-09", interval="5m")

# 멀티인덱스를 단일 레벨로 변환
if isinstance(data.columns, pd.MultiIndex):
    data.columns = data.columns.get_level_values(0)

# backtesting.py 요구 컬럼명 매핑
data = data.rename(
    columns={
        "Open": "Open",
        "High": "High",
        "Low": "Low",
        "Close": "Close",
        "Volume": "Volume",
    }
)

bt = FractionalBacktest(
    data, DMIStrategy, cash=1000000, commission=0.001, exclusive_orders=False, hedging=True
)

stats = bt.run()
print(stats)
bt.plot()
