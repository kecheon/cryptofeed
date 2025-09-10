import numpy as np
from backtesting import Strategy
from ta.trend import ADXIndicator


class DMIStrategy(Strategy):
    adx_period = 14
    threshold = 25
    take_profit = 0.01      # 개별 포지션 1% 익절
    total_exit = 0.003        # 헷지 상태에서 전체 수익률 2% 이상이면 청산
    initial_size_pct = 0.000001    # Initial trade size as a percentage of equity
    hedge_multiplier = 2.5       # Multiplies the cash value of the opposing side

    def init(self):
        df = self.data.df
        adx_ind = ADXIndicator(
            high=df["High"], low=df["Low"], close=df["Close"], window=self.adx_period
        )
        self.adx = self.I(lambda: adx_ind.adx().to_numpy())
        self.plus_di = self.I(lambda: adx_ind.adx_pos().to_numpy())
        self.minus_di = self.I(lambda: adx_ind.adx_neg().to_numpy())

    def next(self):
        price = self.data.Close[-1]

        # Debug prints
        print(f"--- Top of next() | Bar: {len(self.data)} ---")
        print(f"Open trades: {len(self.trades)}")
        print(f"Closed trades: {len(self.closed_trades)}")

        # Signals
        long_signal = self.plus_di[-1] > self.minus_di[-1] and self.adx[-1] > self.threshold
        short_signal = self.minus_di[-1] > self.plus_di[-1] and self.adx[-1] > self.threshold

        open_trades = list(self.trades)

        # --- EXIT LOGIC (Based on Gross Margin Invested) ---
        # 1. Global exit for hedged positions
        if len(open_trades) > 1:
            pnl_total = sum(t.pl for t in open_trades)
            margin_used = sum(abs(t.size * t.entry_price) for t in open_trades)
            if margin_used > 0 and pnl_total / margin_used >= self.total_exit:
                print(f"\n=== HEDGE TOTAL EXIT! Total PnL: {pnl_total / margin_used:.2%} ===")
                for t in open_trades:
                    t.close()
                self.list_positions()
                return

        # 2. Individual take-profit for a single position
        if len(open_trades) == 1:
            trade = open_trades[0]
            margin_used = abs(trade.size * trade.entry_price)
            if margin_used > 0 and trade.pl / margin_used >= self.take_profit:
                trade.close()
                self.list_positions()
                return

        # --- ENTRY LOGIC ---
        # 1. Initial Entry
        if not open_trades:
            if long_signal:
                self.buy(size=self.initial_size_pct)
            elif short_signal:
                self.sell(size=self.initial_size_pct)
            self.list_positions()
            return

        # 2. Controlled Martingale Hedge Entry (Fractional Sizing)
        if sum(t.pl for t in open_trades) < 0:  # Only hedge if losing
            long_trades = [t for t in open_trades if t.is_long]
            short_trades = [t for t in open_trades if t.is_short]
            long_size_units = sum(t.size for t in long_trades)
            abs_short_size_units = sum(abs(t.size) for t in short_trades)

            # Add a LONG hedge only if we are NET SHORT
            if long_signal and abs_short_size_units > long_size_units:
                short_value_usd = abs_short_size_units * price
                new_long_cash_size = self.hedge_multiplier * short_value_usd
                size_as_fraction = new_long_cash_size / self.equity
                self.buy(size=min(size_as_fraction, 1.0)) # Cap at 100% equity

            # Add a SHORT hedge only if we are NET LONG
            elif short_signal and long_size_units > abs_short_size_units:
                long_value_usd = long_size_units * price
                new_short_cash_size = self.hedge_multiplier * long_value_usd
                size_as_fraction = new_short_cash_size / self.equity
                self.sell(size=min(size_as_fraction, 1.0)) # Cap at 100% equity

        self.list_positions()

    def list_positions(self):
        # 열린 포지션
        open_trades = self.trades
        print("\n=== OPEN TRADES ===")
        if not open_trades:
            print("No open positions.")
        else:
            for t in open_trades:
                print(
                    f"{'LONG' if t.is_long else 'SHORT'} | "
                    f"Size: {t.size:.4f} | Entry: {t.entry_price:.2f} | "
                    f"PnL: {t.pl:.2f} | PnL %: {t.pl_pct:.2%}"
                )

        # 종료된 포지션
        closed_trades = self.closed_trades
        print("\n=== CLOSED TRADES ===")
        if not closed_trades:
            print("No closed positions yet.")
        else:
            for t in closed_trades:
                exit_price = f"{t.exit_price:.2f}" if t.exit_price is not None else "-"
                pl = f"{t.pl:.2f}" if t.pl is not None else "-"
                pl_pct = f"{t.pl_pct:.2%}" if t.pl_pct is not None else "-"
                print(
                    f"{'LONG' if t.is_long else 'SHORT'} | "
                    f"Size: {t.size:.4f} | Entry: {t.entry_price:.2f} | "
                    f"Exit: {exit_price} | PnL: {pl} | PnL %: {pl_pct}"
                )
