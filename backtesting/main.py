import yfinance as yf
from backtesting import Backtest
from dmi import DMIStrategy
from dmi_stoploss import DMIStopLossStrategy
import pandas as pd

# --- Import Strategy Libraries ---
from entry_signals import ENTRY_SIGNALS
from exit_strategies import EXIT_STRATEGIES
from volatility_filters import VOLATILITY_FILTERS

# ===================================
# ===      CONFIGURATION          ===
# ===================================
# STRATEGY_TO_RUN = DMIStrategy
STRATEGY_TO_RUN = DMIStopLossStrategy
ENTRY_SIGNAL_NAME = 'dmi'
VOLATILITY_FILTER_NAME = 'pct_range'  # Options: 'pct_range', 'atr_ratio', 'stddev_cv', 'none'
EXIT_STRATEGY_NAME = 'profit_trigger'   # Options: 'profit_trigger', 'dismantle', 'defensive_hedge'

# ===================================
# ===      BACKTEST SETUP         ===
# ===================================
CASH = 1000
COMMISSION = 0.0005
LEVERAGE = 10

# ===================================
# ===      HELPER FUNCTIONS       ===
# ===================================
def load_default_params(strategy_params, library, key_name):
    """Loads default parameters from a library into the strategy_params dictionary."""
    if key_name in library:
        for key, value in library[key_name].get('params', {}).items():
            if key not in strategy_params:
                strategy_params[key] = value

def setup_strategy(strategy_class, vol_filter_name):
    """Injects the chosen volatility filter into the strategy class."""
    vol_filter = VOLATILITY_FILTERS[vol_filter_name]
    strategy_class.volatility_filter = vol_filter
    original_init = strategy_class.init

    def new_init(self):
        original_init(self)
        self.volatility_filter['init'](self)

    strategy_class.init = new_init
    return strategy_class

# ===================================
# ===       PARAMETER SETUP       ===
# ===================================

# 1. Base Parameters (Common to all strategies)
strategy_params = {
    'entry_signal_name': ENTRY_SIGNAL_NAME,
    'volatility_filter_name': VOLATILITY_FILTER_NAME,
    'leverage': LEVERAGE,
    'debug_mode': True,
}

# 2. Strategy-specific Parameters
if STRATEGY_TO_RUN == DMIStrategy:
    hedging_enabled = True
    strategy_specific_params = {
        'exit_strategy_name': EXIT_STRATEGY_NAME,
        'initial_size': 3,
        'hedge_multiplier': 2,
        'max_hedge_count': 3,
        # --- Parameter Overrides ---
        'di_gap_threshold': 15,
        'min_range_pct': 0.03,
    }
    strategy_params.update(strategy_specific_params)
    # Load defaults for all components
    load_default_params(strategy_params, ENTRY_SIGNALS, ENTRY_SIGNAL_NAME)
    load_default_params(strategy_params, VOLATILITY_FILTERS, VOLATILITY_FILTER_NAME)
    load_default_params(strategy_params, EXIT_STRATEGIES, EXIT_STRATEGY_NAME)

elif STRATEGY_TO_RUN == DMIStopLossStrategy:
    hedging_enabled = False
    strategy_specific_params = {
        'initial_size': 10,
        'stop_loss_pct': 0.02,
        'take_profit_pct': 0.03,
        # --- Parameter Overrides ---
        'threshold': 25,
        'min_range_pct': 0.03,
    }
    strategy_params.update(strategy_specific_params)
    # Load defaults for all components
    load_default_params(strategy_params, ENTRY_SIGNALS, ENTRY_SIGNAL_NAME)
    load_default_params(strategy_params, VOLATILITY_FILTERS, VOLATILITY_FILTER_NAME)

# ===================================
# ===      BACKTEST EXECUTION     ===
# ===================================

# 1. Download Data
data = yf.download("SOL-USD", start="2025-08-16", end="2025-09-21", interval="5m")
if isinstance(data.columns, pd.MultiIndex):
    data.columns = data.columns.get_level_values(0)
data = data.rename(columns=lambda x: x.capitalize())

# 2. Prepare Strategy Class with Filters
strategy_to_run = setup_strategy(STRATEGY_TO_RUN, VOLATILITY_FILTER_NAME)

# 3. Run Backtest
bt = Backtest(
    data,
    strategy_to_run,
    cash=CASH,
    commission=COMMISSION,
    margin=1 / LEVERAGE,
    exclusive_orders=not hedging_enabled,
    hedging=hedging_enabled
)

stats = bt.run(**strategy_params)
print(stats)