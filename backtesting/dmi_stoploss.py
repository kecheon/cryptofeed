from backtesting import Strategy
from entry_signals import ENTRY_SIGNALS
import pandas as pd

class DMIStopLossStrategy(Strategy):
    # --- Core Parameters ---
    volatility_filter_name = 'none'

    # --- Volatility Filter Params ---
    range_period = 20
    min_range_pct = 0.03
    atr_short_period = 5
    atr_long_period = 50
    atr_ratio_threshold = 0.5

    # --- Risk Management Parameters ---
    initial_size = 1
    stop_loss_pct = 0.01
    take_profit_pct = 0.03

    # --- General Parameters ---
    debug_mode = True

    def init(self):
        print("--- Running DMIStopLossStrategy ---")
        # --- Set Strategy Functions ---
        self.entry_signal = ENTRY_SIGNALS['dmi']
        
        # --- Initialize Indicators ---
        self.entry_signal['init'](self)

    def next(self):
        if self.debug_mode:
            print("\n" + "="*80)
            print(f"--- BAR: {len(self.data)} ---")

        if not self.trades:
            long_signal, short_signal = self.entry_signal['run'](self)

            if long_signal:
                price = self.data.Close[-1]
                sl_price = price * (1 - self.stop_loss_pct)
                tp_price = price * (1 + self.take_profit_pct)
                self.buy(size=self.initial_size, sl=sl_price, tp=tp_price, tag='initial')

            elif short_signal:
                price = self.data.Close[-1]
                sl_price = price * (1 + self.stop_loss_pct)
                tp_price = price * (1 - self.take_profit_pct)
                self.sell(size=self.initial_size, sl=sl_price, tp=tp_price, tag='initial')
        
        if self.debug_mode:
            self.list_positions()

    def list_positions(self):
        if not self.debug_mode:
            return

        print("\n=== OPEN TRADES ===")
        if not self.trades:
            print("No open positions.")
        else:
            for t in self.trades:
                print(f"{t.entry_bar}: {('LONG' if t.is_long else 'SHORT')} | Role: {t.tag or 'unclassified':<12} | Size: {t.size:.4f} | Entry: {t.entry_price:.2f} | PnL: {t.pl:.2f}")

        if self.closed_trades:
            print("\n=== CLOSED TRADES ===")
            for t in self.closed_trades:
                print(f"{t.entry_bar}→{t.exit_bar}: {('LONG' if t.is_long else 'SHORT')} | Role: {t.tag or 'unclassified':<12} | Size: {t.size:.4f} | Entry: {t.entry_price:.2f} | Exit: {t.exit_price:.2f} | PnL: {t.pl:.2f}")
