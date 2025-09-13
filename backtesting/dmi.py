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
    
    # Long-term MA periods for Locked Exit Mode
    lt_ma_fast = 100
    lt_ma_slow = 400
    
    # Max number of hedges before locking
    max_hedge_count = 3

    def init(self):
        # State variables
        self.hedge_count = 0
        self.locked_exit_mode = False
        self.locked_sequence_id = 0

        # Indicators
        df = self.data.df
        adx_indicator = ADXIndicator(high=df['High'], low=df['Low'], close=df['Close'], window=self.adx_period)
        self.adx = self.I(adx_indicator.adx)
        self.plus_di = self.I(adx_indicator.adx_pos)
        self.minus_di = self.I(adx_indicator.adx_neg)
        
        self.fast_ma = self.I(sma, self.data.Close, self.lt_ma_fast)
        self.slow_ma = self.I(sma, self.data.Close, self.lt_ma_slow)

    def next(self):
        # --- LOCKED EXIT MODE ---
        if self.locked_exit_mode:
            if crossover(self.fast_ma, self.slow_ma):
                print(f"\n=== LOCKED EXIT: Golden Cross detected. Closing all SHORT positions. ===")
                for t in self.trades:
                    if t.is_short:
                        t.close()
                self.locked_exit_mode = False
                self.hedge_count = 0
            elif crossover(self.slow_ma, self.fast_ma):
                print(f"\n=== LOCKED EXIT: Death Cross detected. Closing all LONG positions. ===")
                for t in self.trades:
                    if t.is_long:
                        t.close()
                self.locked_exit_mode = False
                self.hedge_count = 0
            self.list_positions()
            return

        # --- NORMAL MODE ---
        long_signal = (self.plus_di[-1] > self.minus_di[-1] and 
                       self.adx[-1] > self.threshold and 
                       self.adx[-1] > self.adx[-2])
        short_signal = (self.minus_di[-1] > self.plus_di[-1] and 
                        self.adx[-1] > self.threshold and
                        self.adx[-1] > self.adx[-2])

        open_trades = list(self.trades)

        if not open_trades:
            self.hedge_count = 0

        # --- EXIT LOGIC ---
        if len(open_trades) > 1:
            pnl_total = sum(t.pl for t in open_trades)
            notional_value = sum(abs(t.size * t.entry_price) for t in open_trades)
            margin_used = notional_value / self.leverage
            if margin_used > 0 and pnl_total / margin_used >= self.total_exit:
                print(f"\n=== HEDGE TOTAL EXIT! Return on Margin: {pnl_total / margin_used:.2%} ===")
                for t in open_trades:
                    t.close()
                self.list_positions()
                return

        if len(open_trades) == 1:
            trade = open_trades[0]
            notional_value = abs(trade.size * trade.entry_price)
            margin_used = notional_value / self.leverage
            if margin_used > 0 and trade.pl / margin_used >= self.take_profit:
                print(f"\n=== INDIVIDUAL TAKE PROFIT! Return on Margin: {trade.pl / margin_used:.2%} ===")
                trade.close()
                self.list_positions()
                return

        # --- ENTRY LOGIC ---
        if not open_trades:
            if long_signal:
                self.buy(size=int(self.initial_size))
            elif short_signal:
                self.sell(size=int(self.initial_size))
            self.list_positions()
            return

        if sum(t.pl for t in open_trades) < 0:
            long_trades = [t for t in open_trades if t.is_long]
            short_trades = [t for t in open_trades if t.is_short]
            long_size_units = sum(t.size for t in long_trades)
            abs_short_size_units = sum(abs(t.size) for t in short_trades)

            if self.hedge_count == self.max_hedge_count - 1:
                net_exposure = long_size_units - abs_short_size_units
                if (short_signal and net_exposure > 0) or (long_signal and net_exposure < 0):
                    print(f"\n=== FINAL HEDGE: Entering Locked Exit Mode. Neutralizing position. ===")
                    self.locked_sequence_id += 1
                    for t in self.trades:
                        t.locked_sequence_id = self.locked_sequence_id
                    if net_exposure > 0:
                        new_trade = self.sell(size=abs(net_exposure))
                    else:
                        new_trade = self.buy(size=abs(net_exposure))
                    if new_trade:
                        new_trade.locked_sequence_id = self.locked_sequence_id
                    self.hedge_count += 1
                    self.locked_exit_mode = True
            
            elif self.hedge_count < self.max_hedge_count - 1:
                if long_signal and abs_short_size_units > long_size_units:
                    new_size = self.hedge_multiplier * abs_short_size_units
                    final_size = max(1, int(math.ceil(new_size)))
                    self.buy(size=final_size)
                    self.hedge_count += 1
                elif short_signal and long_size_units > abs_short_size_units:
                    new_size = self.hedge_multiplier * long_size_units
                    final_size = max(1, int(math.ceil(new_size)))
                    self.sell(size=final_size)
                    self.hedge_count += 1

        self.list_positions()

    def list_positions(self):
        open_trades = self.trades
        print("\n=== OPEN TRADES ===")
        if not open_trades:
            print("No open positions.")
        else:
            for t in open_trades:
                notional_value = abs(t.size * t.entry_price)
                margin_used = notional_value / self.leverage
                pnl_pct_on_margin = t.pl / margin_used if margin_used > 0 else 0
                print(
                    f"{ 'LONG' if t.is_long else 'SHORT'} | "
                    f"Size: {t.size:.4f} | Entry: {t.entry_price:.2f} | "
                    f"PnL: {t.pl:.2f} | PnL % on Margin: {pnl_pct_on_margin:.2%}"
                )

        normal_closed = [t for t in self.closed_trades if not hasattr(t, 'locked_sequence_id')]
        locked_trades = [t for t in self.closed_trades if hasattr(t, 'locked_sequence_id')]

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
                print(
                    f"{ 'LONG' if t.is_long else 'SHORT'} | "
                    f"Size: {t.size:.4f} | Entry: {t.entry_price:.2f} | "
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
                    'locked_sequence_id': t.locked_sequence_id
                })
            df = pd.DataFrame(trade_dicts)
            for seq_id, group in df.groupby('locked_sequence_id'):
                print(f"\n--- Sequence ID: {int(seq_id)} ---")
                total_pnl = group['pl'].sum()
                print(f"  Total PnL for this sequence: {total_pnl:.2f}")
                for _, trade in group.iterrows():
                    notional_value = abs(trade['size'] * trade['entry_price'])
                    margin_used = notional_value / self.leverage
                    pnl_pct_on_margin = trade['pl'] / margin_used if margin_used > 0 else 0
                    direction = 'LONG' if trade['size'] > 0 else 'SHORT'
                    print(
                        f"  {direction} | "
                        f"Size: {trade['size']:.4f} | Entry: {trade['entry_price']:.2f} | "
                        f"Exit: {trade['exit_price']:.2f} | PnL: {trade['pl']:.2f} | PnL % on Margin: {pnl_pct_on_margin:.2%}"
                    )
        else:
            print("No locked sequence positions closed yet.")