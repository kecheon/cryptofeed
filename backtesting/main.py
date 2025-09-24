import yfinance as yf
from backtesting import Backtest
from dmi import DMIStrategy
from dmi_stoploss import DMIStopLossStrategy
import pandas as pd

# --- Import Strategy Libraries ---
from entry_signals import ENTRY_SIGNALS
from exit_strategies import EXIT_STRATEGIES
from volatility_filters import VOLATILITY_FILTERS


# Download data
data = yf.download("SOL-USD", start="2025-08-16", end="2025-09-21", interval="5m")

if isinstance(data.columns, pd.MultiIndex):
    data.columns = data.columns.get_level_values(0)

data = data.rename(columns=lambda x: x.capitalize())

# --- Backtest Configuration ---
cash = 1000
commission = 0.0005
leverage = 10

# ===================================
# === CONFIGURATION ===
# ===================================
STRATEGY_TO_RUN = DMIStopLossStrategy
# STRATEGY_TO_RUN = DMIStrategy
ENTRY_SIGNAL_NAME = 'dmi'
VOLATILITY_FILTER_NAME = 'pct_range' #'stddev_cv' # 'pct_range', 'atr_ratio', or 'none'
# VOLATILITY_FILTER_NAME = 'stddev_cv' # 'pct_range', 'atr_ratio', or 'none'
# ===================================

# --- Parameter Loading Function ---
def load_default_params(strategy_params, library, key_name):
    if key_name in library:
        for key, value in library[key_name].get('params', {}).items():
            if key not in strategy_params:
                strategy_params[key] = value

# --- Strategy-specific Parameters ---
if STRATEGY_TO_RUN == DMIStrategy:
    EXIT_STRATEGY_NAME = 'profit_trigger'
    hedging_enabled = True

    strategy_params = {
        'entry_signal_name': ENTRY_SIGNAL_NAME,
        'exit_strategy_name': EXIT_STRATEGY_NAME,
        'volatility_filter_name': VOLATILITY_FILTER_NAME,
        'leverage': leverage,
        'debug_mode': True,
        'initial_size': 3,
        'hedge_multiplier': 2,
        'max_hedge_count': 3,
        # --- Entry Signal Overrides ---
        'di_gap_threshold': 15,
        # --- Volatility Filter Overrides ---
        'range_period':  20,
        'min_range_pct': 0.03,
        'atr_ratio_threshold': 0.5,
        'stddev_period': 20,
        'min_cv_threshold': 0.003,
    }
    load_default_params(strategy_params, ENTRY_SIGNALS, ENTRY_SIGNAL_NAME)
    load_default_params(strategy_params, VOLATILITY_FILTERS, VOLATILITY_FILTER_NAME)
    load_default_params(strategy_params, EXIT_STRATEGIES, EXIT_STRATEGY_NAME)

elif STRATEGY_TO_RUN == DMIStopLossStrategy:
    hedging_enabled = False
    strategy_params = {
        'entry_signal_name': ENTRY_SIGNAL_NAME,
        'volatility_filter_name': VOLATILITY_FILTER_NAME,
        'debug_mode': True,
        'initial_size': 10,
        'stop_loss_pct': 0.02,
        'take_profit_pct': 0.03,
        # --- Entry Signal Overrides ---
        'threshold': 20,
        'di_gap_threshold': 15,
        # --- Volatility Filter Overrides ---
        'range_period':  20,
        'min_range_pct': 0.03,
        'atr_ratio_threshold': 0.5,
        'stddev_period': 20,
        'min_cv_threshold': 0.01,
    }
    load_default_params(strategy_params, ENTRY_SIGNALS, ENTRY_SIGNAL_NAME)
    load_default_params(strategy_params, VOLATILITY_FILTERS, VOLATILITY_FILTER_NAME)

# --- Inject filter functions into strategy class ---
# This is a bit of a hack, but it decouples the logic nicely.
vol_filter = VOLATILITY_FILTERS[VOLATILITY_FILTER_NAME]
STRATEGY_TO_RUN.volatility_filter = vol_filter
original_init = STRATEGY_TO_RUN.init

def new_init(self):
    # Call original init first
    original_init(self)
    # Then initialize indicators for the selected volatility filter
    self.volatility_filter['init'](self)

STRATEGY_TO_RUN.init = new_init

# --- Backtest Execution ---
bt = Backtest(
    data,
    STRATEGY_TO_RUN,
    cash=cash,
    commission=commission,
    margin=1 / leverage,
    exclusive_orders=not hedging_enabled,
    hedging=hedging_enabled
)

stats = bt.run(**strategy_params)
print(stats)
