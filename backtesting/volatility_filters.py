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

def check_stddev_cv(strategy):
    """Checks if the market is ranging based on the Coefficient of Variation of price."""
    if strategy.sma_vol[-1] == 0: # Avoid division by zero
        return False
    normalized_volatility = strategy.std_vol[-1] / strategy.sma_vol[-1]
    return normalized_volatility < strategy.min_cv_threshold

def check_volume_surge(strategy):
    """This is an entry confirmation filter. It returns False if volume is NOT surging."""
    is_surging = strategy.data.Volume[-1] > (strategy.volume_sma[-1] * strategy.volume_surge_multiplier)
    return not is_surging

def check_z_score(strategy):
    """Checks if the current price is within a normal volatility range using Z-Score."""
    if strategy.z_std[-1] == 0: # Avoid division by zero
        return True # If std is zero, it's definitely ranging (below lower threshold)
    z_score = abs((strategy.data.Close[-1] - strategy.z_sma[-1]) / strategy.z_std[-1])
    # Return True (is_ranging) if z_score is outside the desired range
    return not (strategy.z_score_lower_threshold < z_score < strategy.z_score_upper_threshold)

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

def init_stddev_cv_indicators(strategy):
    """Initializes indicators needed for the stddev_cv filter."""
    close = pd.Series(strategy.data.Close)
    strategy.sma_vol = strategy.I(lambda: close.rolling(strategy.stddev_period).mean(), name="SMA_Volatility")
    strategy.std_vol = strategy.I(lambda: close.rolling(strategy.stddev_period).std(), name="STD_Volatility")

def init_volume_surge_indicators(strategy):
    """Initializes indicators needed for the volume_surge filter."""
    volume = pd.Series(strategy.data.Volume)
    strategy.volume_sma = strategy.I(lambda: volume.rolling(strategy.volume_sma_period).mean(), name="SMA_Volume")

def init_z_score_indicators(strategy):
    """Initializes indicators needed for the z_score filter."""
    close = pd.Series(strategy.data.Close)
    strategy.z_sma = strategy.I(lambda: close.rolling(strategy.z_score_period).mean(), name="Z_SMA")
    strategy.z_std = strategy.I(lambda: close.rolling(strategy.z_score_period).std(), name="Z_STD")

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
    'stddev_cv': {
        'init': init_stddev_cv_indicators,
        'run': check_stddev_cv,
        'params': {
            'stddev_period': 20,
            'min_cv_threshold': 0.01
        }
    },
    'volume_surge': {
        'init': init_volume_surge_indicators,
        'run': check_volume_surge,
        'params': {
            'volume_sma_period': 20,
            'volume_surge_multiplier': 2.0
        }
    },
    'z_score': {
        'init': init_z_score_indicators,
        'run': check_z_score,
        'params': {
            'z_score_period': 20,
            'z_score_lower_threshold': 1.5,
            'z_score_upper_threshold': 3.0
        }
    },
    'none': {
        'init': lambda strategy: None, # No indicators to init
        'run': lambda strategy: False, # Always returns False (not ranging)
        'params': {}
    }
}