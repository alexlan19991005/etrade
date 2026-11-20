"""Defensive rotation across SPY / TLT / BIL (long-term).

Daily regime switch on 200-day averages: SPY above its average -> SPY;
else TLT above its average -> TLT; else BIL (cash). Wins in long bear
markets and rate-cutting cycles; loses in fast V-shaped recoveries and in
joint stock/bond sell-offs (2022-style), when it sits in cash while both
recover.

Parameters: ma_window=200 on daily closes.
"""

import pandas as pd

from .base import BaseStrategy


class DefensiveRotationStrategy(BaseStrategy):
    name = "defensive_rotation"
    symbols = ["SPY", "TLT", "BIL"]

    def __init__(self, ma_window: int = 200):
        self.ma_window = ma_window

    def generate_signals(
        self, prices: pd.DataFrame, data: dict | None = None
    ) -> pd.DataFrame:
        spy = prices["SPY"]
        tlt = prices["TLT"]
        spy_ma = spy.rolling(self.ma_window).mean()
        tlt_ma = tlt.rolling(self.ma_window).mean()
        w = pd.DataFrame(0.0, index=prices.index, columns=self.symbols)
        # NaN comparisons are False, so before 200 days of history the
        # portfolio simply stays in cash.
        w.loc[(spy > spy_ma).fillna(False), "SPY"] = 1.0
        w.loc[
            ((spy <= spy_ma) & (tlt > tlt_ma)).fillna(False), "TLT"
        ] = 1.0
        w.loc[
            ((spy <= spy_ma) & (tlt <= tlt_ma)).fillna(False), "BIL"
        ] = 1.0
        return w
