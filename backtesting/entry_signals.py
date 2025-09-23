# entry_signals.py

from ta.trend import ADXIndicator
import pandas as pd

def init_dmi_indicators(strategy):
    """Initializes the indicators needed for the DMI signal."""
    df = pd.DataFrame({
        'High': strategy.data.High,
        'Low': strategy.data.Low,
        'Close': strategy.data.Close
    })
    adx_indicator = ADXIndicator(high=df['High'], low=df['Low'], close=df['Close'], window=strategy.adx_period)
    strategy.adx = strategy.I(lambda: adx_indicator.adx(), name="ADX")
    strategy.plus_di = strategy.I(lambda: adx_indicator.adx_pos(), name="Plus DI")
    strategy.minus_di = strategy.I(lambda: adx_indicator.adx_neg(), name="Minus DI")
    # --- Volatility Range Filter Indicators ---
    strategy.highest_high = strategy.I(lambda x: pd.Series(x).rolling(strategy.range_period).max(), strategy.data.High, name="HighestHigh")
    strategy.lowest_low = strategy.I(lambda x: pd.Series(x).rolling(strategy.range_period).min(), strategy.data.Low, name="LowestLow")

def run_dmi_signal(strategy):
    """Generates entry signals based on the DMI and ADX indicators."""
    # --- Debug Print: Check the actual threshold value being used ---
    # Print once a day to avoid flooding the log
    if strategy.data.index[-1].hour == 0 and strategy.data.index[-1].minute == 0:
        print(f"Bar {len(strategy.data)}: Checking signals with threshold = {strategy.threshold}")

    # --- Volatility Range Filter ---
    highest_high = strategy.highest_high[-1]
    lowest_low = strategy.lowest_low[-1]
    is_ranging = ((highest_high - lowest_low) / lowest_low) < strategy.min_range_pct

    # --- Original DMI/ADX Signal ---
    long_signal_dmi = (
        strategy.plus_di[-1] > strategy.minus_di[-1] and
        (strategy.plus_di[-1] - strategy.minus_di[-1]) > strategy.di_gap_threshold and
        strategy.adx[-1] > strategy.threshold and
        strategy.adx[-1] > strategy.adx[-2] # ADX Rising
    )
    short_signal_dmi = (
        strategy.minus_di[-1] > strategy.plus_di[-1] and
        (strategy.minus_di[-1] - strategy.plus_di[-1]) > strategy.di_gap_threshold and
        strategy.adx[-1] > strategy.threshold and
        strategy.adx[-1] > strategy.adx[-2] # ADX Rising
    )

    # --- Final Signal --- 
    long_signal = long_signal_dmi and not is_ranging
    short_signal = short_signal_dmi and not is_ranging

    return long_signal, short_signal

# ===================================
# === ENTRY SIGNAL REGISTRY ===
# ===================================
ENTRY_SIGNALS = {
    'dmi': {
        'init': init_dmi_indicators,
        'run': run_dmi_signal
    },
}