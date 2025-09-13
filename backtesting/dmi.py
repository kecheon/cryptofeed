import numpy as np
import pandas as pd
from backtesting import Strategy
from backtesting.lib import crossover
from ta.trend import ADXIndicator
import math

def sma(series, n):
    """Helper for calculating a Simple Moving Average"""
    return pd.Series(series).rolling(n).mean()

class DMIStrategy(Strategy):
    # Strategy Parameters
    adx_period = 14
    threshold = 25
    take_profit = 0.01
    total_exit = 0.005
    initial_size = 1
    hedge_multiplier = 2.0
    leverage = 1.0
    debug_mode = True
    max_hedge_count = 3
    dismantle_pct = 0.25

    def init(self):
        # State variables
        self.hedge_count = 0
        self.locked_exit_mode = False
        self.locked_sequence_id = 0
        self.dismantle_side = None

        # Indicators
        df = self.data.df
        adx_indicator = ADXIndicator(high=df['High'], low=df['Low'], close=df['Close'], window=self.adx_period)
        self.adx = self.I(adx_indicator.adx)
        self.plus_di = self.I(adx_indicator.adx_pos)
        self.minus_di = self.I(adx_indicator.adx_neg)
        
        self.fast_ma = self.I(sma, self.data.Close, 100)
        self.slow_ma = self.I(sma, self.data.Close, 400)

    def next(self):
        if self.debug_mode:
            print("="*80)
            print(f"--- BAR: {len(self.data)} | HEDGES: {self.hedge_count} | LOCKED: {self.locked_exit_mode} | DISMANTLE: {self.dismantle_side} ---")

        # --- State Reset --- (If all positions are closed)
        if not self.trades:
            if self.hedge_count > 0 or self.locked_exit_mode:
                self.hedge_count = 0
                self.locked_exit_mode = False
                self.dismantle_side = None

        # --- Signals ---
        long_signal = (self.plus_di[-1] > self.minus_di[-1] and self.adx[-1] > self.threshold and self.adx[-1] > self.adx[-2])
        short_signal = (self.minus_di[-1] > self.plus_di[-1] and self.adx[-1] > self.threshold and self.adx[-1] > self.adx[-2])

        # --- Main State Machine ---
        if self.locked_exit_mode:
            # --- LOCKED EXIT MODE (Take Profits & Wait) ---
            long_trades = [t for t in self.trades if t.is_long]
            short_trades = [t for t in self.trades if t.is_short]

            if not long_trades or not short_trades:
                # This means one side is fully closed. Let the normal exit logic handle the rest.
                pass
            else:
                if self.dismantle_side is None:
                    long_pnl = sum(t.pl for t in long_trades)
                    short_pnl = sum(t.pl for t in short_trades)
                    self.dismantle_side = 'short' if short_pnl > long_pnl else 'long'

                if self.dismantle_side == 'short' and long_signal:
                    abs_short_size_units = sum(abs(t.size) for t in short_trades)
                    size_to_close_float = abs_short_size_units * self.dismantle_pct
                    size_to_close_int = max(1, int(math.ceil(size_to_close_float)))
                    if self.debug_mode:
                        print(f"\n=== LOCKED EXIT: Long signal. Taking profit on {size_to_close_int} SHORT units. ===")
                    
                    trades_before = len(self.trades)
                    self.buy(size=size_to_close_int, tag='dismantle')
                    if len(self.trades) > trades_before:
                        new_trade = self.trades[-1]
                        new_trade.locked_sequence_id = self.locked_sequence_id

                    self.dismantle_side = 'long'
                
                elif self.dismantle_side == 'long' and short_signal:
                    long_size_units = sum(t.size for t in long_trades)
                    size_to_close_float = long_size_units * self.dismantle_pct
                    size_to_close_int = max(1, int(math.ceil(size_to_close_float)))
                    if self.debug_mode:
                        print(f"\n=== LOCKED EXIT: Short signal. Taking profit on {size_to_close_int} LONG units. ===")

                    trades_before = len(self.trades)
                    self.sell(size=size_to_close_int, tag='dismantle')
                    if len(self.trades) > trades_before:
                        new_trade = self.trades[-1]
                        new_trade.locked_sequence_id = self.locked_sequence_id

                    self.dismantle_side = 'short'
        else:
            # --- NORMAL MODE ---
            open_trades = list(self.trades)
            if not open_trades:
                if long_signal:
                    self.buy(size=int(self.initial_size), tag='initial')
                elif short_signal:
                    self.sell(size=int(self.initial_size), tag='initial')
            elif sum(t.pl for t in open_trades) < 0:
                long_trades = [t for t in open_trades if t.is_long]
                short_trades = [t for t in open_trades if t.is_short]
                long_size_units = sum(t.size for t in long_trades)
                abs_short_size_units = sum(abs(t.size) for t in short_trades)

                # Decide if a hedge is needed
                hedge_needed = False
                if long_signal and abs_short_size_units > long_size_units:
                    hedge_needed = True
                elif short_signal and long_size_units > abs_short_size_units:
                    hedge_needed = True

                if hedge_needed:
                    self.hedge_count += 1 # Increment hedge_count BEFORE placing the trade
                    if self.debug_mode: print(f"### HEDGE COUNT INCREMENTED TO: {self.hedge_count} ###")

                    if self.hedge_count == self.max_hedge_count: # Now check if it's the final hedge
                        net_exposure = long_size_units - abs_short_size_units
                        if self.debug_mode:
                            print(f"\n=== FINAL HEDGE: Entering Locked Sequence. Neutralizing position. ===")
                        
                        self.locked_sequence_id += 1
                        for t in self.trades:
                            t.locked_sequence_id = self.locked_sequence_id

                        trades_before = len(self.trades)
                        if net_exposure > 0:
                            self.sell(size=abs(net_exposure), tag='neutralizing')
                        elif net_exposure < 0:
                            self.buy(size=abs(net_exposure), tag='neutralizing')

                        if len(self.trades) > trades_before:
                            new_trade = self.trades[-1]
                            new_trade.locked_sequence_id = self.locked_sequence_id
                        
                        self.locked_exit_mode = True # LOCK ENGAGED
                        self.dismantle_side = None
                    elif self.hedge_count < self.max_hedge_count: # Normal martingale hedge
                        if long_signal and abs_short_size_units > long_size_units:
                            new_size = self.hedge_multiplier * abs_short_size_units
                            final_size = max(1, int(math.ceil(new_size)))
                            self.buy(size=final_size, tag='hedge')
                        elif short_signal and long_size_units > abs_short_size_units:
                            new_size = self.hedge_multiplier * long_size_units
                            final_size = max(1, int(math.ceil(new_size)))
                            self.sell(size=final_size, tag='hedge')

        # --- UNIVERSAL EXIT LOGIC (Applies to all modes) ---
        if self.trades:
            open_trades = list(self.trades)
            if len(open_trades) > 1:
                pnl_total = sum(t.pl for t in open_trades)
                notional_value = sum(abs(t.size * t.entry_price) for t in open_trades)
                margin_used = notional_value / self.leverage
                if margin_used > 0 and pnl_total / margin_used >= self.total_exit:
                    if self.debug_mode:
                        print(f"\n=== HEDGE TOTAL EXIT! Return on Margin: {pnl_total / margin_used:.2%} ===")
                    self.position.close()
            elif len(open_trades) == 1:
                trade = open_trades[0]
                notional_value = abs(trade.size * trade.entry_price)
                margin_used = notional_value / self.leverage
                if margin_used > 0 and trade.pl / margin_used >= self.take_profit:
                    if self.debug_mode:
                        print(f"\n=== INDIVIDUAL TAKE PROFIT! Return on Margin: {trade.pl / margin_used:.2%} ===")
                    trade.close()

        if self.debug_mode:
            self.list_positions()

    def list_positions(self):
        open_trades = self.trades
        if self.debug_mode:
            print("\n=== OPEN TRADES ===")
            if not open_trades:
                print("No open positions.")
            else:
                for t in open_trades:
                    notional_value = abs(t.size * t.entry_price)
                    margin_used = notional_value / self.leverage
                    pnl_pct_on_margin = t.pl / margin_used if margin_used > 0 else 0
                    role = t.tag or 'unclassified'
                    print(
                        f"{'LONG' if t.is_long else 'SHORT'} | "
                        f"Role: {role:<12} | Size: {t.size:.4f} | Entry: {t.entry_price:.2f} | "
                        f"PnL: {t.pl:.2f} | PnL % on Margin: {pnl_pct_on_margin:.2%}"
                    )

        normal_closed = [t for t in self.closed_trades if not hasattr(t, 'locked_sequence_id')]
        locked_trades = [t for t in self.closed_trades if hasattr(t, 'locked_sequence_id')]

        if self.debug_mode:
            print("\n=== CLOSED TRADES (NORMAL) ===")
            if not normal_closed:
                print("No normal positions closed yet.")
            else:
                for t in normal_closed:
                    notional_value = abs(t.size * t.entry_price)
                    margin_used = notional_value / self.leverage
                    pnl_pct_on_margin = t.pl / margin_used if margin_used > 0 else 0
                    exit_price = f"{t.exit_price:.2f}" if t.exit_price is not None else "-"
                    pl = f"{t.pl:.2f}" if t.pl is not None else "-"
                    role = t.tag or 'unclassified'
                    print(
                        f"{'LONG' if t.is_long else 'SHORT'} | "
                        f"Role: {role:<12} | Size: {t.size:.4f} | Entry: {t.entry_price:.2f} | "
                        f"Exit: {exit_price} | PnL: {pl} | PnL % on Margin: {pnl_pct_on_margin:.2%}"
                    )

            print("\n=== CLOSED TRADES (FROM LOCKED SEQUENCES) ===")
            if locked_trades:
                trade_dicts = []
                for t in locked_trades:
                    trade_dicts.append({
                        'size': t.size,
                        'entry_price': t.entry_price,
                        'exit_price': t.exit_price,
                        'pl': t.pl,
                        'locked_sequence_id': getattr(t, 'locked_sequence_id', 0),
                        'role': t.tag or 'unclassified'
                    })
                df = pd.DataFrame(trade_dicts)
                for seq_id, group in df.groupby('locked_sequence_id'):
                    if seq_id == 0: continue
                    print(f"\n--- Sequence ID: {int(seq_id)} ---")
                    total_pnl = group['pl'].sum()
                    print(f"  Total PnL for this sequence: {total_pnl:.2f}")
                    for _, trade in group.iterrows():
                        notional_value = abs(trade['size'] * trade['entry_price'])
                        margin_used = notional_value / self.leverage
                        pnl_pct_on_margin = trade['pl'] / margin_used if margin_used > 0 else 0
                        direction = 'LONG' if trade['size'] > 0 else 'SHORT'
                        role = trade['role']
                        print(
                            f"  {direction} | "
                            f"Role: {role:<12} | Size: {trade['size']:.4f} | Entry: {trade['entry_price']:.2f} | "
                            f"Exit: {trade['exit_price']:.2f} | PnL: {trade['pl']:.2f} | PnL % on Margin: {pnl_pct_on_margin:.2%}"
                        )
            else:
                print("No locked sequence positions closed yet.")
