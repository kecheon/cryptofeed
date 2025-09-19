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
    long_signal = strategy.plus_di[-1] > strategy.minus_di[-1] and strategy.adx[-1] > strategy.threshold and strategy.adx[-1] > strategy.adx[-2]
    short_signal = strategy.minus_di[-1] > strategy.plus_di[-1] and strategy.adx[-1] > strategy.threshold and strategy.adx[-1] > strategy.adx[-2]
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