"""
Copyright (C) 2017-2023 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
"""
from cryptofeed import FeedHandler

# from cryptofeed.exchanges import Coinbase, Gemini, Kraken
from cryptofeed.exchanges import Binance, OKX, Bitget, Upbit


def nbbo_update(symbol, bid, bid_size, ask, ask_size, bid_feed, ask_feed):
    spread = 100 * abs(ask - bid) / bid
    bidQty = bid * bid_size
    askQty = ask * ask_size
    if (spread > 0.08) & (bidQty > 100.0) & (askQty > 100.0):
        print(
            f"Pair: {symbol} Spread: {spread:.4f}% Best Bid Price: {bid:.4f} Best Bid Size: {bid_size:.6f} Best Bid Exchange: {bid_feed}\nBest Ask Price: {ask:.4f} Best Ask Size: {ask_size:.6f} Best Ask Feed: {ask_feed}\n"
        )


def main():
    f = FeedHandler(
        config={"log": {"filename": "demo.log", "level": "DEBUG", "disabled": False}}
    )
    f.add_nbbo(
        [Binance, OKX, Bitget],
        [
            "BTC-USDT",
            "ETH-USDT",
            "XRP-USDT",
            "TRX-USDT",
            "ADA-USDT",
            "DOGE-USDT",
            "BCH-USDT",
            "EOS-USDT",
            "LTC-USDT",
            "DOT-USDT",
            "SOL-USDT",
            "MATIC-USDT",
            "AAVE-USDT",
            "ATOM-USDT",
            "MANA-USDT",
            "ONE-USDT",
            "FTM-USDT",
        ],
        nbbo_update,
    )
    f.run()


if __name__ == "__main__":
    main()
