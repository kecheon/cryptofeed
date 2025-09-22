from backtesting import Backtest, Strategy
import pandas as pd

# Dummy data, content doesn't matter
data = pd.DataFrame({'Open': [100]*10, 'High': [100]*10, 'Low': [100]*10, 'Close': [100]*10, 'Volume': [100]*10})

class MarginTestStrategy(Strategy):
    def init(self):
        print("\n" + "="*80)
        print("--- MARGIN FAILURE TEST ---")
        print(f"Initial Equity: {self.equity:.2f}")
        
        # Attempt to place an impossibly large order
        print("Attempting to buy an impossibly large size (e.g., 1,000,000 units)...")
        trade = self.buy(size=1_000_000)
        
        print(f"\n--- TEST RESULTS ---")
        print(f"The returned object is: {repr(trade)}")
        print(f"The type of the returned object is: {type(trade)}")

        print("\n--- Inspecting the Order object's attributes ---")
        if trade:
            # Print all attributes of the Order object to find a status indicator
            for attr in dir(trade):
                if not attr.startswith('__'):
                    try:
                        print(f"  .{attr} = {getattr(trade, attr)}")
                    except Exception as e:
                        print(f"  .{attr} = <Error reading attribute: {e}>") 
        
        print("="*80 + "\n")

    def next(self):
        # Stop the backtest immediately after the first bar
        self.position.close()

bt = Backtest(data, MarginTestStrategy, cash=1000, commission=0.0)
bt.run()
