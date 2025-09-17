import numpy as np
import pandas as pd
from backtesting import Strategy
from backtesting.lib import crossover
from ta.trend import ADXIndicator
import math

from entry_signals import ENTRY_SIGNALS

def sma(series, n):
    """Helper for calculating a Simple Moving Average"""
    return pd.Series(series).rolling(n).mean()

class DMIStrategy(Strategy):
    # --- Strategy Parameters ---
    entry_signal_name = 'dmi'
    adx_period = 14
    threshold = 25
    take_profit = 0.01
    total_exit = 0.005
    initial_size = 1
    hedge_multiplier = 2.0
    leverage = 1.0
    debug_mode = True
    max_hedge_count = 5
    dismantle_pct = 0.25

    def init(self):
        # --- State Variables ---
        self.hedge_count = 0
        self.locked_exit_mode = False
        self.locked_sequence_id = 0
        self.dismantle_side = None
        self.dismantled_trades_log = []

        # --- Set Strategy Functions ---
        self.entry_signal = ENTRY_SIGNALS[self.entry_signal_name]

        # --- Indicators ---
        df = pd.DataFrame({
            'High': self.data.High,
            'Low': self.data.Low,
            'Close': self.data.Close
        })
        adx_indicator = ADXIndicator(high=df['High'], low=df['Low'], close=df['Close'], window=self.adx_period)
        self.adx = self.I(lambda: adx_indicator.adx(), name="ADX")
        self.plus_di = self.I(lambda: adx_indicator.adx_pos(), name="Plus DI")
        self.minus_di = self.I(lambda: adx_indicator.adx_neg(), name="Minus DI")

    def next(self):
        if self.debug_mode:
            print("="*80)
            dismantle_target = 'None'
            if self.dismantle_side:
                dismantle_target = f"{self.dismantle_side.capitalize()} Side"
            print(f"--- BAR: {len(self.data)} | HEDGES: {self.hedge_count} | LOCKED: {self.locked_exit_mode} | TARGETING: {dismantle_target} ---")

        # --- State Reset ---
        if not self.trades and (self.hedge_count > 0 or self.locked_exit_mode):
            self.hedge_count = 0
            self.locked_exit_mode = False
            self.dismantle_side = None
            self.dismantled_trades_log = []

        long_signal, short_signal = self.entry_signal(self)

        if self.locked_exit_mode:
            # --- LOCKED EXIT MODE (Dismantle) ---
            long_trades = [t for t in self.trades if t.is_long and t.tag != 'dismantle']
            short_trades = [t for t in self.trades if t.is_short and t.tag != 'dismantle']

            if not long_trades or not short_trades:
                return

            if self.dismantle_side is None:
                long_pnl = sum(t.pl for t in long_trades)
                short_pnl = sum(t.pl for t in short_trades)
                self.dismantle_side = 'short' if short_pnl > long_pnl else 'long'

            if self.dismantle_side == 'short' and long_signal:
                short_size = sum(t.size for t in short_trades)
                short_value = sum(t.size * t.entry_price for t in short_trades)
                avg_short_price = short_value / short_size if short_size != 0 else 0
                size_to_close = max(1, int(math.ceil(abs(short_size) * self.dismantle_pct)))
                exit_price = self.data.Close[-1]
                realized_pnl = size_to_close * (avg_short_price - exit_price)
                self.dismantled_trades_log.append({
                    'side': 'SHORT', 'size': -size_to_close, 'entry_price': avg_short_price,
                    'exit_price': exit_price, 'pnl': realized_pnl, 'timestamp': self.data.index[-1]
                })
                self.buy(size=size_to_close, tag='dismantle')
                self.dismantle_side = 'long'
            
            elif self.dismantle_side == 'long' and short_signal:
                long_size = sum(t.size for t in long_trades)
                long_value = sum(t.size * t.entry_price for t in long_trades)
                avg_long_price = long_value / long_size if long_size > 0 else 0
                size_to_close = max(1, int(math.ceil(long_size * self.dismantle_pct)))
                exit_price = self.data.Close[-1]
                realized_pnl = size_to_close * (exit_price - avg_long_price)
                self.dismantled_trades_log.append({
                    'side': 'LONG', 'size': size_to_close, 'entry_price': avg_long_price,
                    'exit_price': exit_price, 'pnl': realized_pnl, 'timestamp': self.data.index[-1]
                })
                self.sell(size=size_to_close, tag='dismantle')
                self.dismantle_side = 'short'
        else:
            # --- NORMAL MODE (Hedging) ---
            if not self.trades:
                if long_signal:
                    self.buy(size=int(self.initial_size), tag='initial')
                elif short_signal:
                    self.sell(size=int(self.initial_size), tag='initial')
            elif sum(t.pl for t in self.trades) < 0:
                long_trades = [t for t in self.trades if t.is_long]
                short_trades = [t for t in self.trades if t.is_short]
                long_size_units = sum(t.size for t in long_trades)
                abs_short_size_units = sum(abs(t.size) for t in short_trades)

                hedge_needed = (long_signal and abs_short_size_units > long_size_units) or \
                               (short_signal and long_size_units > abs_short_size_units)

                if hedge_needed:
                    self.hedge_count += 1
                    if self.hedge_count == self.max_hedge_count:
                        self.locked_sequence_id += 1
                        for t in self.trades:
                            t.locked_sequence_id = self.locked_sequence_id
                        
                        trades_before = len(self.trades)
                        if long_size_units > abs_short_size_units:
                            self.sell(size=(long_size_units - abs_short_size_units), tag='neutralizing')
                        elif abs_short_size_units > long_size_units:
                            self.buy(size=(abs_short_size_units - long_size_units), tag='neutralizing')

                        if len(self.trades) > trades_before:
                            self.trades[-1].locked_sequence_id = self.locked_sequence_id
                        
                        self.locked_exit_mode = True
                        self.dismantle_side = None
                    else:
                        if long_signal:
                            self.buy(size=max(1, int(math.ceil(self.hedge_multiplier * abs_short_size_units))), tag='hedge')
                        elif short_signal:
                            self.sell(size=max(1, int(math.ceil(self.hedge_multiplier * long_size_units))), tag='hedge')

        if self.trades:
            if len(self.trades) > 1 and sum(t.pl for t in self.trades) / (sum(abs(t.size * t.entry_price) for t in self.trades) / self.leverage) >= self.total_exit:
                self.position.close()
            elif len(self.trades) == 1 and self.trades[0].pl / (abs(self.trades[0].size * self.trades[0].entry_price) / self.leverage) >= self.take_profit:
                self.trades[0].close()

        if self.debug_mode:
            self.list_positions()

    def list_positions(self):
        if not self.debug_mode:
            return

        print("\n=== POSITIONS OVERVIEW ===")

        open_base_trades = [t for t in self.trades if t.tag != 'dismantle']
        
        total_dismantled_long_size = sum(log['size'] for log in self.dismantled_trades_log if log['side'] == 'LONG')
        total_dismantled_short_size = sum(log['size'] for log in self.dismantled_trades_log if log['side'] == 'SHORT')

        base_long_trades = [t for t in open_base_trades if t.is_long]
        base_short_trades = [t for t in open_base_trades if t.is_short]

        base_long_size = sum(t.size for t in base_long_trades)
        base_short_size = sum(t.size for t in base_short_trades)
        
        display_long_size = base_long_size - total_dismantled_long_size
        display_short_size = base_short_size - total_dismantled_short_size

        if display_long_size > 0.0001:
            net_long_value = sum(t.size * t.entry_price for t in base_long_trades)
            avg_long_price = net_long_value / base_long_size if base_long_size > 0 else 0
            unrealized_long_pnl = sum(t.pl for t in base_long_trades)
            print(f"LONG  | Size: {display_long_size:<10.4f} | Avg Entry: {avg_long_price:<8.2f} | Unrealized PnL: {unrealized_long_pnl:<8.2f}")

        if display_short_size < -0.0001:
            net_short_value = sum(t.size * t.entry_price for t in base_short_trades)
            avg_short_price = net_short_value / base_short_size if base_short_size != 0 else 0
            unrealized_short_pnl = sum(t.pl for t in base_short_trades)
            print(f"SHORT | Size: {display_short_size:<10.4f} | Avg Entry: {avg_short_price:<8.2f} | Unrealized PnL: {unrealized_short_pnl:<8.2f}")
        
        print("\n=== REALIZED DISMANTLE LOG ===")
        if not self.dismantled_trades_log:
            print("No dismantle actions have been logged yet.")
        else:
            total_realized_pnl = 0
            for log in self.dismantled_trades_log:
                total_realized_pnl += log['pnl']
                print(f"{log['timestamp']} | {log['side']:<5} | Size: {log['size']:<8.4f} | Entry: {log['entry_price']:<8.2f} | Exit: {log['exit_price']:<8.2f} | PnL: {log['pnl']:.2f}")
            print(f"------------------------------------------------------------------")
            print(f"Total Realized PnL from Dismantling: {total_realized_pnl:.2f}")

        normal_closed = [t for t in self.closed_trades if not hasattr(t, 'locked_sequence_id')]
        if normal_closed:
            print("\n=== CLOSED TRADES (NORMAL) ===")
            for t in normal_closed:
                print(f"{('LONG' if t.is_long else 'SHORT')} | Role: {t.tag or 'unclassified':<12} | Size: {t.size:.4f} | Entry: {t.entry_price:.2f} | Exit: {t.exit_price:.2f} | PnL: {t.pl:.2f}")