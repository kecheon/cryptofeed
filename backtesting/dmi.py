import numpy as np
import pandas as pd
from backtesting import Strategy
from backtesting.lib import crossover
from ta.trend import ADXIndicator
import math

from entry_signals import ENTRY_SIGNALS
from exit_strategies import EXIT_STRATEGIES

class StrategyCriticalError(Exception):
    """Custom exception for critical strategy failures."""
    pass   

def sma(series, n):
    """Helper for calculating a Simple Moving Average"""
    return pd.Series(series).rolling(n).mean()

# --- Helper functions for new tag structure ---
def get_trade_role(trade):
    if isinstance(trade.tag, dict):
        return trade.tag.get('role', 'unclassified')
    return trade.tag or 'unclassified'

def get_locked_sequence_id(trade):
    if isinstance(trade.tag, dict):
        seq_id = trade.tag.get('locked_sequence_id')
        if seq_id is not None:
            return seq_id
    if hasattr(trade, 'locked_sequence_id'):
        return trade.locked_sequence_id
    return None

class DMIStrategy(Strategy):
    # --- Strategy Core Parameters ---
    entry_signal_name = 'dmi'
    exit_strategy_name = 'dismantle'
    volatility_filter_names = []
    adx_period = 14
    adx_upper_threshold = 30
    threshold = 25
    partial_sl_pct = 0.3 # For cut-and-rehedge logic

    # --- Risk & Sizing ---
    take_profit = 0.01
    total_exit = 0.005
    initial_size = 1
    hedge_multiplier = 2.0
    leverage = 1.0
    debug_mode = True
    max_hedge_count = 5
    entry_cooldown_period = 1

    # --- Exit Strategy Params ---
    dismantle_pct = 0.25
    defensive_hedge_pct = 0.5
    profit_trigger_threshold = 0.01
    profit_realization_pct = 1.0

    # --- Entry Signal Params ---
    di_gap_threshold = 5

    # --- Volatility Filter Params ---
    range_period = 20
    min_range_pct = 0.03
    atr_short_period = 5
    atr_long_period = 50
    atr_ratio_threshold = 0.5
    stddev_period = 20
    min_cv_threshold = 0.01
    volume_sma_period = 20
    volume_surge_multiplier = 2.0

    # --- Z-Score Filter Params ---
    z_score_period = 20
    z_score_lower_threshold = 1.5
    z_score_upper_threshold = 3.0

    # --- Debugging Params ---
    debug_bar_number = 0

    # --- Dummy params for compatibility ---
    # stop_loss_pct = 0.01
    # take_profit_pct = 0.02

    def init(self):
        print("--- Running DMIStrategy (Hedging) ---")
        # --- State Variables ---
        self.hedge_count = 0
        self.locked_exit_mode = False
        self.locked_sequence_id = 0
        self.dismantle_side = None
        self.dismantled_trades_log = []
        self.last_defensive_action_side = None
        self.rehedge_pending_side = None
        self.last_exit_bar = 0
        self._last_closed_trades_len = 0

        # --- Set Strategy Functions ---
        self.entry_signal = ENTRY_SIGNALS[self.entry_signal_name]
        self.exit_strategy = EXIT_STRATEGIES[self.exit_strategy_name]['function']
        
        # --- Initialize Indicators ---
        self.entry_signal['init'](self)

    def _cut_and_rehedge(self, long_signal, short_signal):
        """Step 1: Initiate a partial close if in a single-sided position and an opposing signal occurs."""
        long_trades = [t for t in self.trades if t.is_long]
        short_trades = [t for t in self.trades if t.is_short]

        if long_trades and not short_trades and short_signal:
            if self.debug_mode:
                print(f"\n=== CUT & RE-HEDGE (Step 1): Opposing signal found. Initiating partial close of LONG side. ===\n")
            
            total_long_size = sum(t.size for t in long_trades)
            size_to_close = math.floor(total_long_size * self.partial_sl_pct)
            if size_to_close > 0:
                close_pct = size_to_close / total_long_size
                for trade in long_trades:
                    trade.close(close_pct)
            
            self.rehedge_pending_side = 'long'

        elif short_trades and not long_trades and long_signal:
            if self.debug_mode:
                print(f"\n=== CUT & RE-HEDGE (Step 1): Opposing signal found. Initiating partial close of SHORT side. ===\n")
            
            total_short_size = abs(sum(t.size for t in short_trades))
            size_to_close = math.floor(total_short_size * self.partial_sl_pct)
            if size_to_close > 0:
                close_pct = size_to_close / total_short_size
                for trade in short_trades:
                    trade.close(close_pct)

            self.rehedge_pending_side = 'short'

    def next(self):
        current_bar = len(self.data)

        if len(self.closed_trades) > self._last_closed_trades_len:
            self.last_exit_bar = current_bar - 1
        self._last_closed_trades_len = len(self.closed_trades)

        if self.debug_mode:
            dismantle_target = 'None'
            if self.dismantle_side:
                dismantle_target = f"{self.dismantle_side.capitalize()} Side"
            print("\n" + "="*80)
            print(f"--- BAR: {current_bar} | HEDGES: {self.hedge_count} | LOCKED: {self.locked_exit_mode} | TARGETING: {dismantle_target} ---")

        margin_used = sum(abs(t.size * t.entry_price) / self.leverage for t in self.trades)
        available_margin = self.equity - margin_used

        if not self.trades and (self.hedge_count > 0 or self.locked_exit_mode):
            self.hedge_count = 0
            self.locked_exit_mode = False
            self.dismantle_side = None
            self.last_defensive_action_side = None

        long_signal, short_signal = self.entry_signal['run'](self)

        if self.debug_bar_number > 0:
            print("\n" + "#"*20 + f" DEBUGGING BAR {current_bar} " + "#"*20)
            print(f"[BAR {current_bar}] Current Open Trades: {self.trades}")
            print(f"[Signal {current_bar}] long_signal: {long_signal}")
            print(f"[Signal {current_bar}] short_signal: {short_signal}")

            not_ranging = self.volatility_filter['run'](self)
            cond1 = self.minus_di[-1] > self.plus_di[-1]
            cond2 = abs(self.minus_di[-1] - self.plus_di[-1]) > self.di_gap_threshold
            cond3 = self.adx[-1] > self.threshold
            cond4 = self.adx[-1] > self.adx[-2]
            final_signal = cond1 and cond2 and cond3 and cond4 and not_ranging

            print(f"[BAR {current_bar}] SIGNAL VALIDATION:")
            if long_signal:
                cond1 = self.minus_di[-1] < self.plus_di[-1]
                print(f"  -DI ({self.minus_di[-1]:.2f}) < +DI ({self.plus_di[-1]:.2f}) : {cond1}")
            elif short_signal:
                cond1 = self.minus_di[-1] > self.plus_di[-1]
                print(f"  -DI ({self.minus_di[-1]:.2f}) > +DI ({self.plus_di[-1]:.2f}) : {cond1}")
  
            print(f"  DI Gap > {self.di_gap_threshold:.2f} : {cond2}")
            print(f"  ADX ({self.adx[-1]:.2f}) > Threshold ({self.threshold:.2f}) : {cond3}")
            print(f"  ADX Rising (current > prev) : {cond4}")
            print(f"  NOT Ranging (Filter Pass) : {not_ranging}")
            print(f"  ==> FINAL SIGNAL: {final_signal}")
            if current_bar == self.debug_bar_number + 2:
                raise SystemExit(f"--- DEBUG: Intentionally stopped after bar {current_bar} for validation. ---")

        if self.locked_exit_mode:
            if self.rehedge_pending_side is not None:
                if self.rehedge_pending_side == 'long':
                    remaining_long_size = sum(t.size for t in self.trades if t.is_long)
                    if self.debug_mode:
                        print(f"\n=== CUT & RE-HEDGE (Step 2): Re-hedging remaining LONG size of {remaining_long_size} ===\n")
                    if remaining_long_size > 0:
                        self.sell(size=remaining_long_size, tag={'role': 're_hedge', 'locked_sequence_id': self.locked_sequence_id})
                elif self.rehedge_pending_side == 'short':
                    remaining_short_size = abs(sum(t.size for t in self.trades if t.is_short))
                    if self.debug_mode:
                        print(f"\n=== CUT & RE-HEDGE (Step 2): Re-hedging remaining SHORT size of {remaining_short_size} ===\n")
                    if remaining_short_size > 0:
                        self.buy(size=remaining_short_size, tag={'role': 're_hedge', 'locked_sequence_id': self.locked_sequence_id})
                self.rehedge_pending_side = None
            else:
                self.exit_strategy(self)
                self._cut_and_rehedge(long_signal, short_signal)

        else:
            if not self.trades:
                can_enter = (current_bar - self.last_exit_bar) > self.entry_cooldown_period
                if can_enter:
                    if long_signal:
                        size = int(self.initial_size)
                        price = self.data.Close[-1]
                        required_margin = (size * price) / self.leverage
                        if required_margin > available_margin:
                            raise StrategyCriticalError(f"CRITICAL ERROR at bar {current_bar}: Insufficient margin for INITIAL trade. Required: {required_margin:.2f}, Available: {available_margin:.2f}")
                        self.buy(size=size, tag={'role': 'initial'})
                    elif short_signal:
                        size = int(self.initial_size)
                        price = self.data.Close[-1]
                        required_margin = (size * price) / self.leverage
                        if required_margin > available_margin:
                            raise StrategyCriticalError(f"CRITICAL ERROR at bar {current_bar}: Insufficient margin for INITIAL trade. Required: {required_margin:.2f}, Available: {available_margin:.2f}")
                        self.sell(size=size, tag={'role': 'initial'})
            elif sum(t.pl for t in self.trades) < 0:
                long_trades = [t for t in self.trades if t.is_long]
                short_trades = [t for t in self.trades if t.is_short]
                long_size_units = sum(t.size for t in long_trades)
                abs_short_size_units = sum(abs(t.size) for t in short_trades)

                hedge_needed = (long_signal and abs_short_size_units > long_size_units) or \
                               (short_signal and long_size_units > abs_short_size_units)

                if hedge_needed and self.max_hedge_count > 0:
                    self.hedge_count += 1
                    if self.hedge_count == self.max_hedge_count:
                        self.locked_sequence_id += 1
                        for t in self.trades:
                            t.locked_sequence_id = self.locked_sequence_id
                        
                        price = self.data.Close[-1]
                        if long_size_units > abs_short_size_units:
                            size = long_size_units - abs_short_size_units
                            required_margin = (size * price) / self.leverage
                            if required_margin > available_margin:
                                raise StrategyCriticalError(f"CRITICAL ERROR at bar {current_bar}: Insufficient margin for NEUTRALIZING trade. Required: {required_margin:.2f}, Available: {available_margin:.2f}")
                            self.sell(size=size, tag={'role': 'neutralizing', 'locked_sequence_id': self.locked_sequence_id})
                        elif abs_short_size_units > long_size_units:
                            size = abs_short_size_units - long_size_units
                            required_margin = (size * price) / self.leverage
                            if required_margin > available_margin:
                                raise StrategyCriticalError(f"CRITICAL ERROR at bar {current_bar}: Insufficient margin for NEUTRALIZING trade. Required: {required_margin:.2f}, Available: {available_margin:.2f}")
                            self.buy(size=size, tag={'role': 'neutralizing', 'locked_sequence_id': self.locked_sequence_id})
                        
                        self.locked_exit_mode = True
                        self.dismantle_side = None

                    else:
                        price = self.data.Close[-1]
                        if long_signal:
                            size = max(1, int(math.ceil(self.hedge_multiplier * abs_short_size_units)))
                            required_margin = (size * price) / self.leverage
                            if required_margin > available_margin:
                                raise StrategyCriticalError(f"CRITICAL ERROR at bar {current_bar}: Insufficient margin for HEDGE trade. Required: {required_margin:.2f}, Available: {available_margin:.2f}")
                            self.buy(size=size, tag={'role': 'hedge'})
                        elif short_signal:
                            size = max(1, int(math.ceil(self.hedge_multiplier * long_size_units)))
                            required_margin = (size * price) / self.leverage
                            if required_margin > available_margin:
                                raise StrategyCriticalError(f"CRITICAL ERROR at bar {current_bar}: Insufficient margin for HEDGE trade. Required: {required_margin:.2f}, Available: {available_margin:.2f}")
                            self.sell(size=size, tag={'role': 'hedge'})

        if self.trades:
            if len(self.trades) > 1 and self.hedge_count > 0 and sum(t.pl for t in self.trades) / (sum(abs(t.size * t.entry_price) for t in self.trades) / self.leverage) >= self.total_exit:
                self.position.close()
            elif len(self.trades) == 1 and self.hedge_count == 0:
                trade = self.trades[0]
                if trade.pl > 0 and ((trade.is_long and short_signal) or (trade.is_short and long_signal)):
                    trade.close()
                elif trade.pl / (abs(trade.size * trade.entry_price) / self.leverage) >= self.take_profit:
                    trade.close()
                elif self.max_hedge_count == 0 and trade.pl < 0:
                    if trade.is_long and short_signal:
                        trade.close()
                    elif trade.is_short and long_signal:
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
                role = get_trade_role(t)
                print(f"{t.entry_bar}: {('LONG' if t.is_long else 'SHORT')} | Role: {role:<12} | Size: {t.size:.4f} | Entry: {t.entry_price:.2f} | PnL: {t.pl:.2f}")

        normal_closed = [t for t in self.closed_trades if get_locked_sequence_id(t) is None]
        if normal_closed:
            print("\n=== CLOSED TRADES (NORMAL) ===")
            for t in normal_closed:
                role = get_trade_role(t)
                print(f"{t.entry_bar}→{t.exit_bar}: {('LONG' if t.is_long else 'SHORT')} | Role: {role:<12} | Size: {t.size:.4f} | Entry: {t.entry_price:.2f} | Exit: {t.exit_price:.2f} | PnL: {t.pl:.2f}")

        locked_trades = [t for t in self.closed_trades if get_locked_sequence_id(t) is not None]
        if locked_trades:
            print("\n=== CLOSED TRADES (FROM LOCKED SEQUENCES) ===")
            df = pd.DataFrame([{'size': t.size, 'entry_price': t.entry_price, 'exit_price': t.exit_price,
                                'pl': t.pl, 'locked_sequence_id': get_locked_sequence_id(t), 'role': get_trade_role(t), 
                                'entry_bar': t.entry_bar, 'exit_bar': t.exit_bar}
                               for t in locked_trades])
            for seq_id, group in df.groupby('locked_sequence_id'):
                print(f"\n--- Sequence ID: {int(seq_id)} ---")
                print(f"  Total PnL for this sequence: {group['pl'].sum():.2f}")
                for _, trade in group.iterrows():
                    direction = 'LONG' if trade['size'] > 0 else 'SHORT'
                    print(f"  {trade['entry_bar']}→{trade['exit_bar']}: {direction} | Role: {trade['role']:<12} | Size: {trade['size']:.4f} | Entry: {trade['entry_price']:.2f} | Exit: {trade['exit_price']:.2f} | PnL: {trade['pl']:.2f}")
