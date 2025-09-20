import yfinance as yf
from backtesting import Backtest
from dmi import DMIStrategy
from dmi_defensive import DMIDefensiveStrategy # Import the new strategy
import pandas as pd

# --- Import Strategy Libraries ---
from entry_signals import ENTRY_SIGNALS
from exit_strategies import EXIT_STRATEGIES


# Download data
data = yf.download("SOL-USD", start="2025-08-16", end="2025-09-15", interval="5m")

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
import yfinance as yf
from backtesting import Backtest
from dmi import DMIStrategy
import pandas as pd

# --- Import Strategy Libraries ---
from entry_signals import ENTRY_SIGNALS
from exit_strategies import EXIT_STRATEGIES


# Download data
data = yf.download("SOL-USD", start="2025-08-16", end="2025-09-15", interval="5m")

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
EXIT_STRATEGY_NAME = 'defensive_hedge' #'dismantle' # Now you can choose 'dismantle' or 'defensive_hedge'
# ===================================

# --- Strategy Parameters ---
# Core parameters shared by all strategies
strategy_params = {
    'entry_signal_name': ENTRY_SIGNAL_NAME,
    'exit_strategy_name': EXIT_STRATEGY_NAME,
    'leverage': leverage,
    'max_hedge_count': 3,
    'take_profit': 0.01,
    'total_exit': 0.005,
    'initial_size': 1,
    'hedge_multiplier': 2,
    'debug_mode': True,
    # Add other core params here
}

# Add parameters specific to the chosen exit strategy
if EXIT_STRATEGY_NAME in EXIT_STRATEGIES:
    strategy_params.update(EXIT_STRATEGIES[EXIT_STRATEGY_NAME]['params'])

# Add parameters specific to the chosen entry signal
if ENTRY_SIGNAL_NAME in ENTRY_SIGNALS:
    # Assuming entry signals might have params in the future
    if 'params' in ENTRY_SIGNALS[ENTRY_SIGNAL_NAME]:
        strategy_params.update(ENTRY_SIGNALS[ENTRY_SIGNAL_NAME]['params'])


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
# ===================================

# --- Strategy Parameters ---
# Core parameters shared by all strategies
strategy_params = {
    'entry_signal_name': ENTRY_SIGNAL_NAME,
    'exit_strategy_name': EXIT_STRATEGY_NAME,
    'leverage': leverage,
    'max_hedge_count': 1,
    'take_profit': 0.01,
    'total_exit': 0.005,
    'initial_size': 1,
    'hedge_multiplier': 2,
    'debug_mode': True,
    'dismantle_pct': 0.5,
    'defensive_hedge_pct': 0.9,
    # Add other core params here
}

# Add parameters specific to the chosen exit strategy
if EXIT_STRATEGY_NAME in EXIT_STRATEGIES:
    strategy_params.update(EXIT_STRATEGIES[EXIT_STRATEGY_NAME]['params'])

# Add parameters specific to the chosen entry signal
if ENTRY_SIGNAL_NAME in ENTRY_SIGNALS:
    # Assuming entry signals might have params in the future
    if 'params' in ENTRY_SIGNALS[ENTRY_SIGNAL_NAME]:
        strategy_params.update(ENTRY_SIGNALS[ENTRY_SIGNAL_NAME]['params'])


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