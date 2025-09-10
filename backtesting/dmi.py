import numpy as np
from backtesting import Strategy
from ta.trend import ADXIndicator
import math

class DMIStrategy(Strategy):
    # Strategy Parameters
    adx_period = 14
    threshold = 25
    take_profit = 0.01      # e.g. 1% on margin
    total_exit = 0.005        # e.g. 0.5% on margin
    initial_size = 1          # In units
    hedge_multiplier = 2.0
    leverage = 1.0            # Default, will be overridden by params from main.py

    def init(self):
        df = self.data.df
        adx_ind = ADXIndicator(
            high=df["High"], low=df["Low"], close=df["Close"], window=self.adx_period
        )
        self.adx = self.I(lambda: adx_ind.adx().to_numpy())
        self.plus_di = self.I(lambda: adx_ind.adx_pos().to_numpy())
        self.minus_di = self.I(lambda: adx_ind.adx_neg().to_numpy())

    def next(self):
        # Debug prints
        print(f"--- Top of next() | Bar: {len(self.data)} ---")
        print(f"Open trades: {len(self.trades)}")
        print(f"Closed trades: {len(self.closed_trades)}")

        # Signals
        long_signal = self.plus_di[-1] > self.minus_di[-1] and self.adx[-1] > self.threshold
        short_signal = self.minus_di[-1] > self.plus_di[-1] and self.adx[-1] > self.threshold

        open_trades = list(self.trades)

        # --- EXIT LOGIC (Based on Margin Used) ---
        # 1. Global exit for hedged positions
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

        # 2. Individual take-profit for a single position
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
        # 1. Initial Entry
        if not open_trades:
            if long_signal:
                self.buy(size=int(self.initial_size))
            elif short_signal:
                self.sell(size=int(self.initial_size))
            self.list_positions()
            return

        # 2. Controlled Martingale Hedge Entry (Integer Sizing)
        if sum(t.pl for t in open_trades) < 0:  # Only hedge if losing
            long_trades = [t for t in open_trades if t.is_long]
            short_trades = [t for t in open_trades if t.is_short]
            long_size_units = sum(t.size for t in long_trades)
            abs_short_size_units = sum(abs(t.size) for t in short_trades)

            # Add a LONG hedge only if we are NET SHORT
            if long_signal and abs_short_size_units > long_size_units:
                new_size = self.hedge_multiplier * abs_short_size_units
                final_size = max(1, int(math.ceil(new_size)))
                self.buy(size=final_size)

            # Add a SHORT hedge only if we are NET LONG
            elif short_signal and long_size_units > abs_short_size_units:
                new_size = self.hedge_multiplier * long_size_units
                final_size = max(1, int(math.ceil(new_size)))
                self.sell(size=final_size)

        self.list_positions()

    def list_positions(self):
        # 열린 포지션
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

        # 종료된 포지션
        closed_trades = self.closed_trades
        print("\n=== CLOSED TRADES ===")
        if not closed_trades:
            print("No closed positions yet.")
        else:
            for t in closed_trades:
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
