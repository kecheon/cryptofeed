# volatility_filters.py

from ta.volatility import AverageTrueRange
import pandas as pd

# ===================================
# === Individual Filter Logics ===
# All `check_` functions return True if the condition PASSES
# ===================================

def check_pct_range(strategy):
    """Returns True if the price range is WIDE enough."""
    highest_high = strategy.highest_high[-1]
    lowest_low = strategy.lowest_low[-1]
    if lowest_low == 0: return True
    return ((highest_high - lowest_low) / lowest_low) >= strategy.min_range_pct

def check_atr_ratio(strategy):
    """Returns True if short-term volatility is HIGH enough compared to long-term."""
    if strategy.atr_long[-1] == 0: return True
    return (strategy.atr_short[-1] / strategy.atr_long[-1]) >= strategy.atr_ratio_threshold

def check_stddev_cv(strategy):
    """Returns True if the Coefficient of Variation is HIGH enough."""
    if strategy.sma_vol[-1] == 0: return True
    normalized_volatility = strategy.std_vol[-1] / strategy.sma_vol[-1]
    return normalized_volatility >= strategy.min_cv_threshold

def check_volume_surge(strategy):
    """Returns True if volume IS surging."""
    if strategy.volume_sma[-1] == 0: return True
    return strategy.data.Volume[-1] > (strategy.volume_sma[-1] * strategy.volume_surge_multiplier)

def check_z_score(strategy):
    """Returns True if the Z-Score is within the desired 'active' range."""
    if strategy.z_std[-1] == 0: return False
    z_score = abs((strategy.data.Close[-1] - strategy.z_sma[-1]) / strategy.z_std[-1])
    return strategy.z_score_lower_threshold < z_score < strategy.z_score_upper_threshold

def check_volume_z_score(strategy):
    """Returns True if the volume Z-Score is high enough."""
    if strategy.volume_z_std[-1] == 0: return False
    z_score = (strategy.data.Volume[-1] - strategy.volume_z_sma[-1]) / strategy.volume_z_std[-1]
    return z_score > strategy.volume_z_score_threshold

def check_vw_z_score(strategy):
    """Returns True if the Volume-Weighted Z-Score is within the desired range."""
    if strategy.vw_z_std[-1] == 0: return False
    current_vw_price = strategy.data.Close[-1] * strategy.data.Volume[-1]
    z_score = abs((current_vw_price - strategy.vw_z_sma[-1]) / strategy.vw_z_std[-1])
    return strategy.vw_z_score_lower_threshold < z_score < strategy.vw_z_score_upper_threshold

# ===================================
# === Filter Initializers ===
# ===================================

def init_pct_range_indicators(strategy):
    """Initializes indicators needed for the pct_range filter."""
    strategy.highest_high = strategy.I(lambda x: pd.Series(x).rolling(strategy.range_period).max(), strategy.data.High, name="HighestHigh")
    strategy.lowest_low = strategy.I(lambda x: pd.Series(x).rolling(strategy.range_period).min(), strategy.data.Low, name="LowestLow")

def init_atr_ratio_indicators(strategy):
    """Initializes indicators needed for the atr_ratio filter."""
    df = pd.DataFrame({'High': strategy.data.High, 'Low': strategy.data.Low, 'Close': strategy.data.Close})
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

def init_volume_z_score_indicators(strategy):
    """Initializes indicators needed for the volume_z_score filter."""
    volume = pd.Series(strategy.data.Volume)
    strategy.volume_z_sma = strategy.I(lambda: volume.rolling(strategy.volume_z_score_period).mean(), name="Volume_Z_SMA")
    strategy.volume_z_std = strategy.I(lambda: volume.rolling(strategy.volume_z_score_period).std(), name="Volume_Z_STD")

def init_vw_z_score_indicators(strategy):
    """Initializes indicators for the Volume-Weighted Z-Score filter."""
    vw_price = pd.Series(strategy.data.Close * strategy.data.Volume)
    strategy.vw_z_sma = strategy.I(lambda: vw_price.rolling(strategy.vw_z_score_period).mean(), name="VW_Z_SMA")
    strategy.vw_z_std = strategy.I(lambda: vw_price.rolling(strategy.vw_z_score_period).std(), name="VW_Z_STD")

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
    'volume_z_score': {
        'init': init_volume_z_score_indicators,
        'run': check_volume_z_score,
        'params': {
            'volume_z_score_period': 20,
            'volume_z_score_threshold': 1.5
        }
    },
    'vw_z_score': {
        'init': init_vw_z_score_indicators,
        'run': check_vw_z_score,
        'params': {
            'vw_z_score_period': 20,
            'vw_z_score_lower_threshold': 1.0,
            'vw_z_score_upper_threshold': 3.0
        }
    },
    'none': {
        'init': lambda strategy: None,
        'run': lambda strategy: True,
        'params': {}
    }
}
