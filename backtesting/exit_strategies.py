# exit_strategies.py

import math

def dismantling_strategy(strategy):
    """Implements the dismantling exit strategy."""
    # ... (existing code) ...

def defensive_hedge_strategy(strategy):
    """Implements the defensive hedge exit strategy."""
    # ... (existing code) ...

def profit_trigger_strategy(strategy):
    """An exit strategy that takes profit and then handles the remaining position by cutting losses and re-hedging."""
    long_trades = [t for t in strategy.trades if t.is_long]
    short_trades = [t for t in strategy.trades if t.is_short]
    long_signal, short_signal = strategy.entry_signal['run'](strategy)

    # Initialize state variables on the strategy object if they don't exist
    if not hasattr(strategy, 'rehedge_pending_side'):
        strategy.rehedge_pending_side = None

    # --- Step 2: Execute Re-Hedge (if pending) ---
    if strategy.rehedge_pending_side is not None:
        if strategy.rehedge_pending_side == 'long':
            remaining_long_size = sum(t.size for t in long_trades)
            if strategy.debug_mode:
                print(f"\n=== PROFIT_TRIGGER (Step 2): Re-hedging remaining LONG size of {remaining_long_size} ===\n")
            if remaining_long_size > 0:
                strategy.sell(size=remaining_long_size, tag={'role': 're_hedge', 'locked_sequence_id': strategy.locked_sequence_id})
        elif strategy.rehedge_pending_side == 'short':
            remaining_short_size = abs(sum(t.size for t in short_trades))
            if strategy.debug_mode:
                print(f"\n=== PROFIT_TRIGGER (Step 2): Re-hedging remaining SHORT size of {remaining_short_size} ===\n")
            if remaining_short_size > 0:
                strategy.buy(size=remaining_short_size, tag={'role': 're_hedge', 'locked_sequence_id': strategy.locked_sequence_id})
        strategy.rehedge_pending_side = None
        return # End execution for this bar

    # --- Step 1: Primary Logic (Take Profit or Partial SL) ---
    long_pnl = sum(t.pl for t in long_trades)
    short_pnl = sum(t.pl for t in short_trades)
    long_notional = sum(t.size * t.entry_price for t in long_trades)
    short_notional = abs(sum(t.size * t.entry_price for t in short_trades))

    # A) Take profit if one side is profitable
    if long_trades and short_trades:
        if long_notional > 0 and (long_pnl / long_notional) > strategy.profit_trigger_threshold and strategy.last_defensive_action_side != 'long':
            if short_signal:
                if strategy.debug_mode:
                    print(f"\n=== PROFIT TRIGGER (Step 1a): LONG side profitable. Closing all LONG trades. ===\n")
                for trade in long_trades:
                    trade.close(strategy.profit_realization_pct)
                strategy.last_defensive_action_side = 'long'
                return
        elif short_notional > 0 and (short_pnl / short_notional) > strategy.profit_trigger_threshold and strategy.last_defensive_action_side != 'short':
            if long_signal:
                if strategy.debug_mode:
                    print(f"\n=== PROFIT TRIGGER (Step 1a): SHORT side profitable. Closing all SHORT trades. ===\n")
                for trade in short_trades:
                    trade.close(strategy.profit_realization_pct)
                strategy.last_defensive_action_side = 'short'
                return

    # B) If not taking profit, check for cut-and-rehedge condition (single-sided position)
    if long_trades and not short_trades and short_signal:
        if strategy.debug_mode:
            print(f"\n=== PROFIT_TRIGGER (Step 1b): Opposing signal found. Initiating partial close of LONG side. ===\n")
        total_long_size = sum(t.size for t in long_trades)
        size_to_close = total_long_size * strategy.partial_sl_pct
        if size_to_close > 0:
            strategy.sell(size=int(size_to_close), tag={'role': 'partial_sl', 'locked_sequence_id': strategy.locked_sequence_id})
        strategy.rehedge_pending_side = 'long'

    elif short_trades and not long_trades and long_signal:
        if strategy.debug_mode:
            print(f"\n=== PROFIT_TRIGGER (Step 1b): Opposing signal found. Initiating partial close of SHORT side. ===\n")
        total_short_size = abs(sum(t.size for t in short_trades))
        size_to_close = total_short_size * strategy.partial_sl_pct
        if size_to_close > 0:
            strategy.buy(size=int(size_to_close), tag={'role': 'partial_sl', 'locked_sequence_id': strategy.locked_sequence_id})
        strategy.rehedge_pending_side = 'short'

# ===================================
# === EXIT STRATEGY REGISTRY ===
# ===================================
EXIT_STRATEGIES = {
    'dismantle': {
        'function': dismantling_strategy,
        'params': {'dismantle_pct': 0.25}
    },
    'defensive_hedge': {
        'function': defensive_hedge_strategy,
        'params': {'defensive_hedge_pct': 0.5}
    },
    'profit_trigger': {
        'function': profit_trigger_strategy,
        'params': {
            'profit_trigger_threshold': 0.02,
            'profit_realization_pct': 1.0,
            'partial_sl_pct': 0.3
        }
    }
}
