# dmi_defensive.py

from dmi import DMIStrategy
import math
import pandas as pd
from entry_signals import ENTRY_SIGNALS

class DMIDefensiveStrategy(DMIStrategy):
    """
    This strategy inherits from DMIStrategy but overrides the next() method
    to implement the "Defensive Hedge" logic instead of the "Dismantle" logic.
    """
    # Add parent parameters to satisfy the library's requirements
    entry_signal_name = 'dmi'
    exit_strategy_name = None

    defensive_hedge_pct = 0.5 # New parameter

    def init(self):
        super().init()
        self.defensive_action_count = 0
        self.defensive_closed_keys = set()
        # This strategy will use the same entry signal module
        self.entry_signal = ENTRY_SIGNALS[self.entry_signal_name]

    def next(self):
        if self.debug_mode:
            print("="*80)
            print(f"--- BAR: {len(self.data)} | HEDGES: {self.hedge_count} | DEFENSIVE_ACTIONS: {self.defensive_action_count} ---")

        # --- State Reset ---
        if not self.trades and self.hedge_count > 0:
            self.hedge_count = 0
            self.defensive_action_count = 0

        long_signal, short_signal = self.entry_signal(self)

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
                if self.debug_mode: print(f"### HEDGE COUNT INCREMENTED TO: {self.hedge_count} ###")

                is_defensive_hedge = self.hedge_count >= self.max_hedge_count

                if long_signal:
                    if is_defensive_hedge:
                        self.defensive_action_count += 1
                        if self.debug_mode: print(f"\n=== DEFENSIVE HEDGE: Trend is UP. Partially closing SHORT side. ===\n")
                        for trade in short_trades:
                            trade_key = (trade.entry_bar, trade.entry_price)
                            self.defensive_closed_keys.add(trade_key)
                            trade.close(self.defensive_hedge_pct)
                    
                    size_to_hedge_against = abs_short_size_units * (1 - self.defensive_hedge_pct) if is_defensive_hedge else abs_short_size_units
                    new_size = self.hedge_multiplier * size_to_hedge_against
                    self.buy(size=max(1, int(math.ceil(new_size))), tag='hedge')

                elif short_signal:
                    if is_defensive_hedge:
                        self.defensive_action_count += 1
                        if self.debug_mode: print(f"\n=== DEFENSIVE HEDGE: Trend is DOWN. Partially closing LONG side. ===\n")
                        for trade in long_trades:
                            trade_key = (trade.entry_bar, trade.entry_price)
                            self.defensive_closed_keys.add(trade_key)
                            trade.close(self.defensive_hedge_pct)

                    size_to_hedge_against = long_size_units * (1 - self.defensive_hedge_pct) if is_defensive_hedge else long_size_units
                    new_size = self.hedge_multiplier * size_to_hedge_against
                    self.sell(size=max(1, int(math.ceil(new_size))), tag='hedge')

        # --- Universal Exit Logic ---
        if self.trades:
            if len(self.trades) > 1:
                pnl_total = sum(t.pl for t in self.trades)
                notional_value = sum(abs(t.size * t.entry_price) for t in self.trades)
                margin_used = notional_value / self.leverage
                if margin_used > 0 and pnl_total / margin_used >= self.total_exit:
                    self.position.close()
            elif len(self.trades) == 1:
                trade = self.trades[0]
                if trade.pl / (abs(trade.size * trade.entry_price) / self.leverage) >= self.take_profit:
                    trade.close()

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
                print(f"{'LONG' if t.is_long else 'SHORT'} | Role: {t.tag or 'unclassified':<12} | Size: {t.size:.4f} | Entry: {t.entry_price:.2f} | PnL: {t.pl:.2f}")

        normal_closed = [t for t in self.closed_trades if not hasattr(t, 'locked_sequence_id')]
        if normal_closed:
            print("\n=== CLOSED TRADES (NORMAL) ===")
            for t in normal_closed:
                trade_key = (t.entry_bar, t.entry_price)
                role = t.tag or 'unclassified'
                if trade_key in self.defensive_closed_keys:
                    role = 'defensive_sl'
                print(f"{'LONG' if t.is_long else 'SHORT'} | Role: {role:<12} | Size: {t.size:.4f} | Entry: {t.entry_price:.2f} | Exit: {t.exit_price:.2f} | PnL: {t.pl:.2f}")

        locked_trades = [t for t in self.closed_trades if hasattr(t, 'locked_sequence_id')]
        if locked_trades:
            print("\n=== CLOSED TRADES (FROM LOCKED SEQUENCES) ===")
            df = pd.DataFrame([
                {'size': t.size, 'entry_price': t.entry_price, 'exit_price': t.exit_price,
                 'pl': t.pl, 'locked_sequence_id': t.locked_sequence_id, 'role': t.tag
                } for t in locked_trades])
            for seq_id, group in df.groupby('locked_sequence_id'):
                print(f"\n--- Sequence ID: {int(seq_id)} ---")
                print(f"  Total PnL for this sequence: {group['pl'].sum():.2f}")
                for _, trade in group.iterrows():
                    direction = 'LONG' if trade['size'] > 0 else 'SHORT'
                    print(f"  {direction} | Role: {trade['role']:<12} | Size: {trade['size']:.4f} | Entry: {trade['entry_price']:.2f} | Exit: {trade['exit_price']:.2f} | PnL: {trade['pl']:.2f}")
