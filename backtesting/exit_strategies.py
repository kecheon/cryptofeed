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

    if strategy.dismantle_side == 'short' and (strategy.plus_di[-1] > strategy.minus_di[-1] and strategy.adx[-1] > strategy.threshold and strategy.adx[-1] > strategy.adx[-2]):
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
    
    elif strategy.dismantle_side == 'long' and (strategy.minus_di[-1] > strategy.plus_di[-1] and strategy.adx[-1] > strategy.threshold and strategy.adx[-1] > strategy.adx[-2]):
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
    """This function is now managed inside the DMIDefensiveStrategy class."""
    pass # This logic is now directly in dmi_defensive.py

# ===================================
# === EXIT STRATEGY REGISTRY ===
# ===================================
EXIT_STRATEGIES = {
    'dismantle': {
        'function': dismantling_strategy,
        'params': {'dismantle_pct': 0.25}
    },
    'defensive_hedge': {
        'function': defensive_hedge_strategy, # This will be overridden in the child class
        'params': {'defensive_hedge_pct': 0.5}
    }
}
