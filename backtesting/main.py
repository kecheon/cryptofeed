import yfinance as yf
from backtesting import Backtest
from dmi import DMIStrategy
import pandas as pd
from backtesting.lib import FractionalBacktest
from dmi_defensive import DMIDefensiveStrategy


# BTCUSD 1시간봉 예시
data = yf.download("SOL-USD", start="2025-08-16", end="2025-09-15", interval="5m")

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

# --- Backtest Configuration ---
cash = 10000
commission = 0.0005
leverage = 10  # Set desired leverage (e.g., 10 for 10x)

# --- Strategy Parameters ---
# Note: Leverage is defined here and also passed to the strategy
# to ensure profit % is calculated against margin, not notional value.
strategy_params = {
    'exit_strategy_name': 'defensive_hedge',
    'adx_period': 14,
    'threshold': 25,
    'take_profit': 0.1,
    'total_exit': 0.05,
    'initial_size': 1,
    'hedge_multiplier': 3,
    'leverage': leverage,
    'max_hedge_count': 3,
    'debug_mode': True,
    'defensive_hedge_pct': 0.3,
}

bt = Backtest(
    data,
    # DMIStrategy,
    DMIDefensiveStrategy,
    cash=cash,
    commission=commission,
    margin=1 / leverage,
    exclusive_orders=False,
    hedging=True,
    finalize_trades=True
)

stats = bt.run(**strategy_params)
print(stats)
# bt.plot()
