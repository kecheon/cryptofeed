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
    exit_strategy_name = 'dismantle' # Add the missing parameter
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
    defensive_hedge_pct = 0.5 # Add for compatibility with child class

    def init(self):
        # --- State Variables ---
        self.hedge_count = 0
        self.locked_exit_mode = False
        self.locked_sequence_id = 0
        self.dismantle_side = None

        # --- Set Strategy Functions ---
        self.entry_signal = ENTRY_SIGNALS[self.entry_signal_name]
        
        # --- Initialize Indicators based on selected signal ---
        self.entry_signal['init'](self)

    def next(self):
        if self.debug_mode:
            dismantle_target = 'None'
            if self.dismantle_side:
                dismantle_target = f"{self.dismantle_side.capitalize()} Side"
            print("\n" + "="*80)
            print(f"--- BAR: {len(self.data)} | HEDGES: {self.hedge_count} | LOCKED: {self.locked_exit_mode} | TARGETING: {dismantle_target} ---")

        if not self.trades and (self.hedge_count > 0 or self.locked_exit_mode):
            self.hedge_count = 0
            self.locked_exit_mode = False
            self.dismantle_side = None

        long_signal, short_signal = self.entry_signal['run'](self)

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
                size_to_close = max(1, int(math.ceil(abs(sum(t.size for t in short_trades)) * self.dismantle_pct)))
                self.buy(size=size_to_close, tag='dismantle')
                self.dismantle_side = 'long'
            
            elif self.dismantle_side == 'long' and short_signal:
                size_to_close = max(1, int(math.ceil(sum(t.size for t in long_trades) * self.dismantle_pct)))
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

        print("\n=== OPEN TRADES ===")
        if not self.trades:
            print("No open positions.")
        else:
            for t in self.trades:
                print(f"{('LONG' if t.is_long else 'SHORT')} | Role: {t.tag or 'unclassified':<12} | Size: {t.size:.4f} | Entry: {t.entry_price:.2f} | PnL: {t.pl:.2f}")

        normal_closed = [t for t in self.closed_trades if not hasattr(t, 'locked_sequence_id')]
        if normal_closed:
            print("\n=== CLOSED TRADES (NORMAL) ===")
            for t in normal_closed:
                print(f"{('LONG' if t.is_long else 'SHORT')} | Role: {t.tag or 'unclassified':<12} | Size: {t.size:.4f} | Entry: {t.entry_price:.2f} | Exit: {t.exit_price:.2f} | PnL: {t.pl:.2f}")

        locked_trades = [t for t in self.closed_trades if hasattr(t, 'locked_sequence_id')]
        if locked_trades:
            print("\n=== CLOSED TRADES (FROM LOCKED SEQUENCES) ===")
            df = pd.DataFrame([{'size': t.size, 'entry_price': t.entry_price, 'exit_price': t.exit_price,
                                'pl': t.pl, 'locked_sequence_id': t.locked_sequence_id, 'role': t.tag}
                               for t in locked_trades])
            for seq_id, group in df.groupby('locked_sequence_id'):
                print(f"\n--- Sequence ID: {int(seq_id)} ---")
                print(f"  Total PnL for this sequence: {group['pl'].sum():.2f}")
                for _, trade in group.iterrows():
                    direction = 'LONG' if trade['size'] > 0 else 'SHORT'
                    print(f"  {direction} | Role: {trade['role']:<12} | Size: {trade['size']:.4f} | Entry: {trade['entry_price']:.2f} | Exit: {trade['exit_price']:.2f} | PnL: {trade['pl']:.2f}")