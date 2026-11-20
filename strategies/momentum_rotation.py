"""Momentum rotation (medium-term): monthly top-5 of 20 liquid large caps.

On the first trading day of each month, rank a fixed universe by 6-month
total return (126 trading days) and hold the top 5 equal-weighted until
the next rebalance. Wins when leadership persists for months; loses on
sharp rotations, and the 5-stock concentration makes it the most volatile
strategy here.

Universe: the largest, most liquid US names — a fixed list, not chosen
with hindsight: AAPL, MSFT, NVDA, AMZN, GOOGL, META, AVGO, JPM, JNJ,
XOM, UNH, HD, PG, MA, LLY, COST, WMT, BAC, AMD, NFLX.

Parameters: lookback=126, top_n=5.
"""

import pandas as pd

from .base import BaseStrategy

UNIVERSE = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "AVGO", "JPM",
    "JNJ", "XOM", "UNH", "HD", "PG", "MA", "LLY", "COST", "WMT",
    "BAC", "AMD", "NFLX",
]


class MomentumRotationStrategy(BaseStrategy):
    name = "momentum_rotation"
    symbols = list(UNIVERSE)

    def __init__(self, lookback: int = 126, top_n: int = 5):
        self.lookback = lookback
        self.top_n = top_n

    def generate_signals(
        self, prices: pd.DataFrame, data: dict | None = None
    ) -> pd.DataFrame:
        closes = prices[self.symbols]
        # 6-month return to day t; pct_change only ever looks backwards.
        rets = closes.pct_change(self.lookback)
        months = prices.index.to_period("M").to_series()
        first_day = months != months.shift(1)
        weights = pd.DataFrame(0.0, index=prices.index, columns=self.symbols)
        current = None
        for i, date in enumerate(prices.index):
            if first_day.iloc[i]:
                ranked = rets.iloc[i].dropna()
                if len(ranked) >= self.top_n:
                    current = ranked.nlargest(self.top_n).index
            if current is not None:
                weights.loc[date, current] = 1.0 / len(current)
        return weights
