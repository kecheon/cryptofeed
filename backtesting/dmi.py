import numpy as np
import pandas as pd
from backtesting import Strategy
from backtesting.lib import crossover
from ta.trend import ADXIndicator
import math

from exit_strategies import EXIT_STRATEGIES

def sma(series, n):
    """Helper for calculating a Simple Moving Average"""
    return pd.Series(series).rolling(n).mean()

class DMIStrategy(Strategy):
    # --- Strategy Parameters ---
    exit_strategy_name = 'dismantle' # Name of the exit strategy to use
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
        # --- State Variables ---
        self.hedge_count = 0
        self.locked_exit_mode = False
        self.locked_sequence_id = 0
        self.dismantle_side = None
        self.dismantled_trades_log = []

        # --- Set the Exit Strategy ---
        self.exit_strategy = EXIT_STRATEGIES[self.exit_strategy_name]

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

        # --- Locked Mode: Execute Exit Strategy ---
        if self.locked_exit_mode:
            self.exit_strategy(self)
        # --- Normal Mode: Hedging Logic ---
        else:
            long_signal = self.plus_di[-1] > self.minus_di[-1] and self.adx[-1] > self.threshold and self.adx[-1] > self.adx[-2]
            short_signal = self.minus_di[-1] > self.plus_di[-1] and self.adx[-1] > self.threshold and self.adx[-1] > self.adx[-2]

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

                    if self.hedge_count == self.max_hedge_count:
                        self.locked_sequence_id += 1
                        for t in self.trades:
                            t.locked_sequence_id = self.locked_sequence_id
                        
                        trades_before = len(self.trades)
                        if long_size_units > abs_short_size_units:
                            size_to_sell = long_size_units - abs_short_size_units
                            self.sell(size=size_to_sell, tag='neutralizing')
                        elif abs_short_size_units > long_size_units:
                            size_to_buy = abs_short_size_units - long_size_units
                            self.buy(size=size_to_buy, tag='neutralizing')

                        if len(self.trades) > trades_before:
                            new_trade = self.trades[-1]
                            new_trade.locked_sequence_id = self.locked_sequence_id
                        
                        self.locked_exit_mode = True
                        self.dismantle_side = None
                    else:
                        if long_signal:
                            new_size = self.hedge_multiplier * abs_short_size_units
                            self.buy(size=max(1, int(math.ceil(new_size))), tag='hedge')
                        elif short_signal:
                            new_size = self.hedge_multiplier * long_size_units
                            self.sell(size=max(1, int(math.ceil(new_size))), tag='hedge')

        # --- Universal Exit Logic ---
        if self.trades:
            if len(self.trades) > 1:
                pnl_total = sum(t.pl for t in self.trades)
                notional_value = sum(abs(t.size * t.entry_price) for t in self.trades)
                margin_used = notional_value / self.leverage
                if margin_used > 0 and pnl_total / margin_used >= self.total_exit:
                    if self.debug_mode:
                        print("\n" + "="*20 + " TOTAL EXIT VERIFICATION " + "="*20)
                        print(f"Total PnL: {pnl_total:.2f}")
                        print(f"Total Margin Used: {margin_used:.2f}")
                        print(f"Return on Margin: {pnl_total / margin_used:.2%}")
                        print(f"Exit Threshold: {self.total_exit:.2%}")
                        print("Condition Met: Exiting all positions.")
                        print("="*65)
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