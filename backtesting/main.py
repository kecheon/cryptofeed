import ccxt
import pandas as pd
from backtesting import Backtest
from dmi import DMIStrategy
from dmi_stoploss import DMIStopLossStrategy
import datetime

# --- Import Strategy Libraries ---
from entry_signals import ENTRY_SIGNALS
from exit_strategies import EXIT_STRATEGIES
from volatility_filters import VOLATILITY_FILTERS


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
# ===      CONFIGURATION          ===
# ===================================
STRATEGY_TO_RUN = DMIStrategy
# STRATEGY_TO_RUN = DMIStopLossStrategy
ENTRY_SIGNAL_NAME = 'dmi'
VOLATILITY_FILTER_NAME = 'z_score'  # Options: 'pct_range', 'atr_ratio', 'stddev_cv', 'none'
EXIT_STRATEGY_NAME = 'profit_trigger' # Options: 'profit_trigger', 'dismantle', 'defensive_hedge'
# ===================================
# ===      BACKTEST SETUP         ===
# ===================================
CASH = 1000
COMMISSION = 0.0005
LEVERAGE = 10
# ===================================
# ===       PARAMETER SETUP       ===
# ===================================

# 1. Base Parameters (Common to all strategies)
strategy_params = {
    'entry_signal_name': ENTRY_SIGNAL_NAME,
    'volatility_filter_name': VOLATILITY_FILTER_NAME,
    'leverage': LEVERAGE,
    'debug_mode': True,
    'debug_bar_number': 0, # Set to a specific bar number to debug, or 0 to disable
    'entry_cooldown_period': 2,
    'adx_period': 14,
    'threshold': 25,
    'adx_upper_threshold': 40,
    'di_gap_threshold': 15,
    'range_period': 20,
    'min_range_pct': 0.03,
    'stddev_period': 20,
    'min_cv_threshold': 0.005,
    'atr_short_period': 5,
    'atr_long_period': 50,
    'atr_ratio_threshold': 0.5,
    'volume_sma_period': 20,
    'volume_surge_multiplier': 2.0,

    # --- Z-Score Filter Params ---
    'z_score_period': 20,
    'z_score_lower_threshold': 1.5,
    'z_score_upper_threshold': 2.0,
}

# 2. Strategy-specific Parameters
if STRATEGY_TO_RUN == DMIStrategy:
    hedging_enabled = True
    strategy_specific_params = {
        'exit_strategy_name': EXIT_STRATEGY_NAME,
        'initial_size': 2,
        'take_profit': 0.01,
        'total_exit' : 0.005,
        'dismantle_pct': 0.25,
        'defensive_hedge_pct': 0.5,
        'hedge_multiplier': 3,
        'max_hedge_count': 3,
        'partial_sl_pct': 0.5, # For cut_and_rehedge strategy
    }
    strategy_params.update(strategy_specific_params)
    # Load defaults for all components
    load_default_params(strategy_params, ENTRY_SIGNALS, ENTRY_SIGNAL_NAME)
    load_default_params(strategy_params, VOLATILITY_FILTERS, VOLATILITY_FILTER_NAME)
    load_default_params(strategy_params, EXIT_STRATEGIES, EXIT_STRATEGY_NAME)

elif STRATEGY_TO_RUN == DMIStopLossStrategy:
    hedging_enabled = False
    strategy_specific_params = {
        'stop_loss_pct': 0.02,
        'take_profit_pct': 0.03,
        'initial_size': 10,
    }
    strategy_params.update(strategy_specific_params)
    # Load defaults for all components
    load_default_params(strategy_params, ENTRY_SIGNALS, ENTRY_SIGNAL_NAME)
    load_default_params(strategy_params, VOLATILITY_FILTERS, VOLATILITY_FILTER_NAME)
# ===================================
# ===      DATA LOADING           ===
# ===================================
SYMBOL = 'SOLUSDT'
TIMEFRAME = '5m'
START_DATE = '2025-08-01T00:00:00Z'

# 1. Initialize exchange
exchange = ccxt.binanceus({
    'options': {'defaultType': 'future'}
})
exchange.load_markets()

# 2. Fetch OHLCV data in a loop
print(f"Fetching {TIMEFRAME} candles for {SYMBOL} from {START_DATE}...")
since = exchange.parse8601(START_DATE)
all_ohlcv = []

while True:
    try:
        ohlcv = exchange.fetch_ohlcv(SYMBOL, TIMEFRAME, since=since, limit=1000)
        if not ohlcv:
            break
        first_ts = ohlcv[0][0]
        last_ts = ohlcv[-1][0]
        print(f"Fetched {len(ohlcv)} candles from {exchange.iso8601(first_ts)} to {exchange.iso8601(last_ts)}")
        all_ohlcv.extend(ohlcv)
        since = last_ts + 1 # Move to the next candle after the last one fetched
    except Exception as e:
        print(f"An error occurred: {e}")
        break

print(f"\nTotal candles fetched: {len(all_ohlcv)}")

# 3. Convert to Pandas DataFrame
data = pd.DataFrame(all_ohlcv, columns=['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])

# 4. Convert timestamp to datetime and set as index
data['Timestamp'] = pd.to_datetime(data['Timestamp'], unit='ms')
data.set_index('Timestamp', inplace=True)

print("Data loaded and formatted successfully.")


# ===================================
# ===      BACKTEST EXECUTION     ===
# ===================================

# 1. Prepare Strategy Class with Filters
strategy_to_run = setup_strategy(STRATEGY_TO_RUN, VOLATILITY_FILTER_NAME)

# 2. Run Backtest
bt = Backtest(
    data,
    strategy_to_run,
    cash=CASH,
    commission=COMMISSION,
    margin=1 / LEVERAGE,
    exclusive_orders=not hedging_enabled,
    hedging=hedging_enabled,
    finalize_trades=True,
)

stats = bt.run(**strategy_params)
print(stats)
# bt.plot(filename="backtest_plot.html")