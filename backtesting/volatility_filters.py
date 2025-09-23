# volatility_filters.py

from ta.volatility import AverageTrueRange
import pandas as pd

# ===================================
# === Individual Filter Logics ===
# ===================================

def check_pct_range(strategy):
    """Checks if the market is ranging based on a fixed percentage of the price range."""
    highest_high = strategy.highest_high[-1]
    lowest_low = strategy.lowest_low[-1]
    if lowest_low == 0: return False # Avoid division by zero
    return ((highest_high - lowest_low) / lowest_low) < strategy.min_range_pct

def check_atr_ratio(strategy):
    """Checks if the market is ranging by comparing short-term ATR to long-term ATR."""
    if strategy.atr_long[-1] == 0: # Avoid division by zero
        return False
    return (strategy.atr_short[-1] / strategy.atr_long[-1]) < strategy.atr_ratio_threshold

# ===================================
# === Filter Initializers ===
# ===================================

def init_pct_range_indicators(strategy):
    """Initializes indicators needed for the pct_range filter."""
    strategy.highest_high = strategy.I(lambda x: pd.Series(x).rolling(strategy.range_period).max(), strategy.data.High, name="HighestHigh")
    strategy.lowest_low = strategy.I(lambda x: pd.Series(x).rolling(strategy.range_period).min(), strategy.data.Low, name="LowestLow")

def init_atr_ratio_indicators(strategy):
    """Initializes indicators needed for the atr_ratio filter."""
    df = pd.DataFrame({
        'High': strategy.data.High,
        'Low': strategy.data.Low,
        'Close': strategy.data.Close
    })
    short_atr_indicator = AverageTrueRange(high=df['High'], low=df['Low'], close=df['Close'], window=strategy.atr_short_period)
    long_atr_indicator = AverageTrueRange(high=df['High'], low=df['Low'], close=df['Close'], window=strategy.atr_long_period)
    strategy.atr_short = strategy.I(lambda: short_atr_indicator.average_true_range(), name="ATR_Short")
    strategy.atr_long = strategy.I(lambda: long_atr_indicator.average_true_range(), name="ATR_Long")

# ===================================
# === VOLATILITY FILTER REGISTRY ===
# ===================================
VOLATILITY_FILTERS = {
    'pct_range': {
        'init': init_pct_range_indicators,
        'run': check_pct_range,
        'params': {
            'range_period': 20,
            'min_range_pct': 0.03
        }
    },
    'atr_ratio': {
        'init': init_atr_ratio_indicators,
        'run': check_atr_ratio,
        'params': {
            'atr_short_period': 5,
            'atr_long_period': 50,
            'atr_ratio_threshold': 0.5
        }
    },
    'none': {
        'init': lambda strategy: None, # No indicators to init
        'run': lambda strategy: False, # Always returns False (not ranging)
        'params': {}
    }
}