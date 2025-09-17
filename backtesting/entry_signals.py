# entry_signals.py

def dmi_signal(strategy):
    """Generates entry signals based on the DMI and ADX indicators."""
    long_signal = strategy.plus_di[-1] > strategy.minus_di[-1] and strategy.adx[-1] > strategy.threshold and strategy.adx[-1] > strategy.adx[-2]
    short_signal = strategy.minus_di[-1] > strategy.plus_di[-1] and strategy.adx[-1] > strategy.threshold and strategy.adx[-1] > strategy.adx[-2]
    return long_signal, short_signal

# ===================================
# === ENTRY SIGNAL REGISTRY ===
# ===================================
ENTRY_SIGNALS = {
    'dmi': dmi_signal,
}
