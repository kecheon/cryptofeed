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

# --- Strategy Parameters ---
strategy_params = {
    'adx_period': 14,
    'threshold': 25,
    'take_profit': 0.01,
    'total_exit': 0.005,
    'initial_size_pct': 0.00001,
    'hedge_multiplier': 2.5,
}

bt = FractionalBacktest(
    data, DMIStrategy, cash=10000, commission=0.0005, exclusive_orders=False, hedging=True
)

stats = bt.run(**strategy_params)
print(stats)
bt.plot()
