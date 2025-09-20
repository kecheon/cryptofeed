# exit_strategies.py

import math

def dismantling_strategy(strategy):
    """Implements the dismantling exit strategy."""
    long_trades = [t for t in strategy.trades if t.is_long and t.tag != 'dismantle']
    short_trades = [t for t in strategy.trades if t.is_short and t.tag != 'dismantle']

    if not long_trades or not short_trades:
        return

    if strategy.dismantle_side is None:
        long_pnl = sum(t.pl for t in long_trades)
        short_pnl = sum(t.pl for t in short_trades)
        strategy.dismantle_side = 'short' if short_pnl > long_pnl else 'long'

    long_signal, short_signal = strategy.entry_signal['run'](strategy)

    if strategy.dismantle_side == 'short' and long_signal:
        short_size = sum(t.size for t in short_trades)
        short_value = sum(t.size * t.entry_price for t in short_trades)
        avg_short_price = short_value / short_size if short_size != 0 else 0
        size_to_close = max(1, int(math.ceil(abs(short_size) * strategy.dismantle_pct)))
        exit_price = strategy.data.Close[-1]
        realized_pnl = size_to_close * (avg_short_price - exit_price)
        strategy.dismantled_trades_log.append({
            'side': 'SHORT', 'size': -size_to_close, 'entry_price': avg_short_price,
            'exit_price': exit_price, 'pnl': realized_pnl, 'timestamp': strategy.data.index[-1]
        })
        strategy.buy(size=size_to_close, tag='dismantle')
        strategy.dismantle_side = 'long'
    
    elif strategy.dismantle_side == 'long' and short_signal:
        long_size = sum(t.size for t in long_trades)
        long_value = sum(t.size * t.entry_price for t in long_trades)
        avg_long_price = long_value / long_size if long_size > 0 else 0
        size_to_close = max(1, int(math.ceil(long_size * strategy.dismantle_pct)))
        exit_price = strategy.data.Close[-1]
        realized_pnl = size_to_close * (exit_price - avg_long_price)
        strategy.dismantled_trades_log.append({
            'side': 'LONG', 'size': size_to_close, 'entry_price': avg_long_price,
            'exit_price': exit_price, 'pnl': realized_pnl, 'timestamp': strategy.data.index[-1]
        })
        strategy.sell(size=size_to_close, tag='dismantle')
        strategy.dismantle_side = 'short'

def defensive_hedge_strategy(strategy):
    """
    Implements the defensive hedge exit strategy.
    This strategy is triggered in locked_exit_mode. It partially closes the losing side of trades
    by placing a single opposing trade.
    """
    long_signal, short_signal = strategy.entry_signal['run'](strategy)
    
    if long_signal and strategy.last_defensive_action_side != 'short':
        short_trades = [t for t in strategy.trades if t.is_short]
        if short_trades:
            if strategy.debug_mode: 
                print(f"\n=== DEFENSIVE HEDGE (Exit Strategy): Trend is UP. Partially closing SHORT side. ===\n")
            total_short_size = abs(sum(t.size for t in short_trades))
            size_to_close = total_short_size * strategy.defensive_hedge_pct
            if size_to_close > 0:
                strategy.buy(size=int(math.ceil(size_to_close)), tag='def_hedge')
                strategy.last_defensive_action_side = 'short'

    elif short_signal and strategy.last_defensive_action_side != 'long':
        long_trades = [t for t in strategy.trades if t.is_long]
        if long_trades:
            if strategy.debug_mode: 
                print(f"\n=== DEFENSIVE HEDGE (Exit Strategy): Trend is DOWN. Partially closing LONG side. ===\n")
            total_long_size = sum(t.size for t in long_trades)
            size_to_close = total_long_size * strategy.defensive_hedge_pct
            if size_to_close > 0:
                strategy.sell(size=int(math.ceil(size_to_close)), tag='def_hedge')
                strategy.last_defensive_action_side = 'long'


def profit_trigger_strategy(strategy):
    """
    An exit strategy that waits for one side of the hedge to become profitable,
    then waits for an opposing signal to realize profits.
    """
    long_trades = [t for t in strategy.trades if t.is_long]
    short_trades = [t for t in strategy.trades if t.is_short]

    if not long_trades or not short_trades:
        return

    long_pnl = sum(t.pl for t in long_trades)
    short_pnl = sum(t.pl for t in short_trades)

    long_notional = sum(t.size * t.entry_price for t in long_trades)
    short_notional = abs(sum(t.size * t.entry_price for t in short_trades))

    long_signal, short_signal = strategy.entry_signal['run'](strategy)

    # Case 1: Long side is profitable, and we haven't just taken profit on the long side
    if long_notional > 0 and (long_pnl / long_notional) > strategy.profit_trigger_threshold and strategy.last_defensive_action_side != 'long':
        if short_signal: # Wait for an opposing (short) signal
            if strategy.debug_mode:
                print(f"\n=== PROFIT TRIGGER: LONG side profitable. Closing {strategy.profit_realization_pct*100}%. ===\n")
            for trade in long_trades:
                trade.locked_sequence_id = strategy.locked_sequence_id
                trade.close(strategy.profit_realization_pct)
            strategy.last_defensive_action_side = 'long'

    # Case 2: Short side is profitable, and we haven't just taken profit on the short side
    elif short_notional > 0 and (short_pnl / short_notional) > strategy.profit_trigger_threshold and strategy.last_defensive_action_side != 'short':
        if long_signal: # Wait for an opposing (long) signal
            if strategy.debug_mode:
                print(f"\n=== PROFIT TRIGGER: SHORT side profitable. Closing {strategy.profit_realization_pct*100}%. ===\n")
            for trade in short_trades:
                trade.locked_sequence_id = strategy.locked_sequence_id
                trade.close(strategy.profit_realization_pct)
            strategy.last_defensive_action_side = 'short'



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
            'profit_trigger_threshold': 0.02, # 2% profit on one side
            'profit_realization_pct': 1.0    # Close 100% of the profitable position
        }
    }
}
