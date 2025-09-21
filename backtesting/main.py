import yfinance as yf
from backtesting import Backtest
from dmi import DMIStrategy
import pandas as pd

# --- Import Strategy Libraries ---
from entry_signals import ENTRY_SIGNALS
from exit_strategies import EXIT_STRATEGIES


# Download data
data = yf.download("SOL-USD", start="2025-08-16", end="2025-09-21", interval="5m")

if isinstance(data.columns, pd.MultiIndex):
    data.columns = data.columns.get_level_values(0)

data = data.rename(columns=lambda x: x.capitalize())

# --- Backtest Configuration ---
cash = 10000
commission = 0.0005
leverage = 10

# ===================================
# === CONFIGURATION ===
# ===================================
STRATEGY_TO_RUN = DMIStrategy
ENTRY_SIGNAL_NAME = 'dmi'
# EXIT_STRATEGY_NAME = 'dismantle'
# EXIT_STRATEGY_NAME = 'defensive_hedge'
EXIT_STRATEGY_NAME = 'profit_trigger' # or 'dismantle' or 'defensive_hedge'
# ===================================

# --- Strategy Parameters ---
# Set core strategy parameters and override defaults here.
strategy_params = {
    # --- Core Params ---
    'entry_signal_name': ENTRY_SIGNAL_NAME,
    'exit_strategy_name': EXIT_STRATEGY_NAME,
    'leverage': leverage,
    'debug_mode': True,

    # --- Strategy Behavior Params ---
    'initial_size': 1,
    'max_hedge_count': 2,
    'hedge_multiplier': 3,
    'take_profit': 0.01,
    'total_exit': 0.005,

    # --- Exit Strategy Params (Overrides) ---
    'dismantle_pct': 0.5,               # Default: 0.25
    'defensive_hedge_pct': 0.5,         # Default: 0.5
    'profit_trigger_threshold': 0.1,   # Default: 0.02 (2%)
    'profit_realization_pct': 1.0,      # Default: 1.0 (100%)
}

# Load default parameters from libraries if they are not set in strategy_params
def load_default_params(strategy_params, library, key_name):
    if key_name in library:
        for key, value in library[key_name].get('params', {}).items():
            if key not in strategy_params:
                strategy_params[key] = value

load_default_params(strategy_params, EXIT_STRATEGIES, EXIT_STRATEGY_NAME)
load_default_params(strategy_params, ENTRY_SIGNALS, ENTRY_SIGNAL_NAME)


bt = Backtest(
    data,
    STRATEGY_TO_RUN,
    cash=cash,
    commission=commission,
    margin=1 / leverage,
    exclusive_orders=False,
    hedging=True
)

stats = bt.run(**strategy_params)
print(stats)
# bt.plot()