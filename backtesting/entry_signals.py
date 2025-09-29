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

def run_dmi_signal(strategy):
    """Generates entry signals based on the DMI and ADX indicators."""
    # --- Debug Print: Check the actual threshold value being used ---
    if strategy.debug_mode and hasattr(strategy, 'threshold') and strategy.data.index[-1].hour == 0 and strategy.data.index[-1].minute == 0:
        print(f"Bar {len(strategy.data)}: Checking signals with threshold = {strategy.threshold}")

    # --- Volatility Filter ---
    # The volatility check is now delegated to the function provided by the strategy
    is_ranging = strategy.volatility_filter['run'](strategy)

    # --- Original DMI/ADX Signal ---
    long_signal_dmi = (
        strategy.plus_di[-1] > strategy.minus_di[-1] and
        (strategy.plus_di[-1] - strategy.minus_di[-1]) > strategy.di_gap_threshold and
        strategy.adx[-1] > strategy.threshold and
        strategy.adx[-1] < strategy.adx_upper_threshold and
        strategy.adx[-1] > strategy.adx[-2] # ADX Rising
    )
    short_signal_dmi = (
        strategy.minus_di[-1] > strategy.plus_di[-1] and
        (strategy.minus_di[-1] - strategy.plus_di[-1]) > strategy.di_gap_threshold and
        strategy.adx[-1] > strategy.threshold and
        strategy.adx[-1] < strategy.adx_upper_threshold and
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
        'run': run_dmi_signal,
        'params': {
            'adx_period': 14,
            'threshold': 25,
            'di_gap_threshold': 5
        }
    },
}
