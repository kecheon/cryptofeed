import yfinance as yf
from backtesting import Backtest
from dmi import DMIStrategy
from dmi_stoploss import DMIStopLossStrategy
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
cash = 1000
commission = 0.0005
leverage = 10

# ===================================
# === CONFIGURATION ===
# ===================================
# Choose which strategy to run by uncommenting one of the lines below
# STRATEGY_TO_RUN = DMIStrategy
STRATEGY_TO_RUN = DMIStopLossStrategy
# ===================================

# --- Parameter Loading Function (for DMIStrategy) ---
def load_default_params(strategy_params, library, key_name):
    if key_name in library:
        for key, value in library[key_name].get('params', {}).items():
            if key not in strategy_params:
                strategy_params[key] = value

# --- Strategy-specific Parameters ---
if STRATEGY_TO_RUN == DMIStrategy:
    # --- Parameters for DMIStrategy (Hedging) ---
    ENTRY_SIGNAL_NAME = 'dmi'
    EXIT_STRATEGY_NAME = 'profit_trigger' # or 'dismantle' or 'defensive_hedge'
    hedging_enabled = True

    strategy_params = {
        # --- Core & Entry Signal ---
        'entry_signal_name': ENTRY_SIGNAL_NAME,
        'exit_strategy_name': EXIT_STRATEGY_NAME,
        'leverage': leverage,
        'debug_mode': True,
        'adx_period': 14,
        'threshold': 25,
        'di_gap_threshold': 15,
        'range_period': 20,
        'atr_period': 14,
        'range_atr_multiplier': 1.5,

        # --- Sizing & Risk (Hedging) ---
        'initial_size': 1,
        'take_profit_pct': 0.02, # Unified name
        'total_exit': 0.005,
        'hedge_multiplier': 2,
        'max_hedge_count': 3,

        # --- Exit Strategy Overrides ---
        'dismantle_pct': 0.5,
        'defensive_hedge_pct': 0.5,
        'profit_trigger_threshold': 0.02,
        'profit_realization_pct': 1.0,
    }
    load_default_params(strategy_params, EXIT_STRATEGIES, EXIT_STRATEGY_NAME)
    load_default_params(strategy_params, ENTRY_SIGNALS, ENTRY_SIGNAL_NAME)

elif STRATEGY_TO_RUN == DMIStopLossStrategy:
    # --- Parameters for DMIStopLossStrategy ---
    hedging_enabled = False
    strategy_params = {
        # --- General & Entry Signal ---
        'debug_mode': True,
        'adx_period': 14,
        'threshold': 25,
        'di_gap_threshold': 5,
        'range_period': 20,
        'atr_period': 14,
        'range_atr_multiplier': 1.5,

        # --- Sizing & Risk (Stop-Loss) ---
        'initial_size': 10,
        'stop_loss_pct': 0.02,
        'take_profit_pct': 0.03,
    }

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
# bt.plot(filename="backtest_plot.html")
