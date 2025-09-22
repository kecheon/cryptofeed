# volatility_filters.py

import pandas as pd

def init_volatility_indicators(strategy):
    """Initializes indicators needed for volatility filters."""
    strategy.highest_high = strategy.I(lambda x: pd.Series(x).rolling(strategy.range_period).max(), strategy.data.High, name="HighestHigh")
    strategy.lowest_low = strategy.I(lambda x: pd.Series(x).rolling(strategy.range_period).min(), strategy.data.Low, name="LowestLow")

def check_min_range_pct(strategy):
    """Checks if the market is ranging based on min_range_pct."""
    highest_high = strategy.highest_high[-1]
    lowest_low = strategy.lowest_low[-1]
    is_ranging = ((highest_high - lowest_low) / lowest_low) < strategy.min_range_pct
    return is_ranging

def check_none(strategy):
    """A dummy filter that always returns False (not ranging)."""
    return False

# ===================================
# === VOLATILITY FILTER REGISTRY ===
# ===================================
VOLATILITY_FILTERS = {
    'min_range_pct': {
        'init': init_volatility_indicators,
        'check': check_min_range_pct,
        'params': {
            'range_period': 20,
            'min_range_pct': 0.03
        }
    },
    'none': {
        'init': lambda strategy: None, # No indicators needed
        'check': check_none,
        'params': {}
    }
}
