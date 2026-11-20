"""50/200-day moving-average crossover on SPY (long-term).

Hold SPY while its 50-day average sits above its 200-day average, else
cash. Wins in long trending bull markets and sits out deep drawdowns;
loses in choppy markets, where repeated crossovers whipsaw, and lags fast
V-shaped recoveries while waiting for the averages to cross back.

Parameters: fast=50, slow=200 (SMA windows on daily closes).
"""

import pandas as pd

from .base import BaseStrategy


class TrendMAStrategy(BaseStrategy):
    name = "trend_ma"
    symbols = ["SPY"]

    def __init__(self, fast: int = 50, slow: int = 200):
        self.fast = fast
        self.slow = slow

    def generate_signals(
        self, prices: pd.DataFrame, data: dict | None = None
    ) -> pd.DataFrame:
        close = prices["SPY"]
        fast = close.rolling(self.fast).mean()
        slow = close.rolling(self.slow).mean()
        w = pd.Series(0.0, index=prices.index)
        w[(fast > slow).fillna(False)] = 1.0
        return pd.DataFrame({"SPY": w}, index=prices.index)
