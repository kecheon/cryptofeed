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

    # --- LOGIC TO DISMANTLE SHORT POSITION ---
    if strategy.dismantle_side == 'short' and (strategy.plus_di[-1] > strategy.minus_di[-1] and strategy.adx[-1] > strategy.threshold and strategy.adx[-1] > strategy.adx[-2]):
        short_size = sum(t.size for t in short_trades)
        short_value = sum(t.size * t.entry_price for t in short_trades)
        avg_short_price = short_value / short_size if short_size != 0 else 0
        
        size_to_close_float = abs(short_size) * strategy.dismantle_pct
        size_to_close_int = max(1, int(math.ceil(size_to_close_float)))
        
        exit_price = strategy.data.Close[-1]
        realized_pnl = size_to_close_int * (avg_short_price - exit_price)
        log_entry = {
            'side': 'SHORT',
            'size': -size_to_close_int,
            'entry_price': avg_short_price,
            'exit_price': exit_price,
            'pnl': realized_pnl,
            'timestamp': strategy.data.index[-1]
        }
        strategy.dismantled_trades_log.append(log_entry)

        if strategy.debug_mode:
            print(f"\n=== DISMANTLING: Closing {size_to_close_int} units of SHORT position at {exit_price:.2f} ===")

        strategy.buy(size=size_to_close_int, tag='dismantle')
        strategy.dismantle_side = 'long'
    
    # --- LOGIC TO DISMANTLE LONG POSITION ---
    elif strategy.dismantle_side == 'long' and (strategy.minus_di[-1] > strategy.plus_di[-1] and strategy.adx[-1] > strategy.threshold and strategy.adx[-1] > strategy.adx[-2]):
        long_size = sum(t.size for t in long_trades)
        long_value = sum(t.size * t.entry_price for t in long_trades)
        avg_long_price = long_value / long_size if long_size > 0 else 0

        size_to_close_float = long_size * strategy.dismantle_pct
        size_to_close_int = max(1, int(math.ceil(size_to_close_float)))

        exit_price = strategy.data.Close[-1]
        realized_pnl = size_to_close_int * (exit_price - avg_long_price)
        log_entry = {
            'side': 'LONG',
            'size': size_to_close_int,
            'entry_price': avg_long_price,
            'exit_price': exit_price,
            'pnl': realized_pnl,
            'timestamp': strategy.data.index[-1]
        }
        strategy.dismantled_trades_log.append(log_entry)

        if strategy.debug_mode:
            print(f"\n=== DISMANTLING: Closing {size_to_close_int} units of LONG position at {exit_price:.2f} ===")

        strategy.sell(size=size_to_close_int, tag='dismantle')
        strategy.dismantle_side = 'short'

# ===================================
# === EXIT STRATEGY REGISTRY ===
# ===================================
EXIT_STRATEGIES = {
    'dismantle': dismantling_strategy,
}
