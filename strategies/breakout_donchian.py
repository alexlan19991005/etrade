"""Donchian breakout on QQQ (medium-short term).

Buy when the close breaks the highest high of the previous 20 days with
volume above its 20-day average; exit on a break of the lowest low of the
previous 10 days. Wins in strong persistent growth trends; loses on false
breakouts in choppy markets.

Parameters: entry_days=20, exit_days=10, volume confirmation on.
"""

import pandas as pd

from .base import BaseStrategy


class BreakoutDonchianStrategy(BaseStrategy):
    name = "breakout_donchian"
    symbols = ["QQQ"]

    def __init__(self, entry_days: int = 20, exit_days: int = 10):
        self.entry_days = entry_days
        self.exit_days = exit_days

    def generate_signals(
        self, prices: pd.DataFrame, data: dict | None = None
    ) -> pd.DataFrame:
        if data is None:
            raise ValueError("breakout_donchian needs high/low/volume data")
        close = prices["QQQ"]
        high = data["high"]["QQQ"]
        low = data["low"]["QQQ"]
        vol = data["volume"]["QQQ"]
        # Prior N days only — shift(1) keeps today out of the channel.
        prev_high = high.shift(1).rolling(self.entry_days).max()
        prev_low = low.shift(1).rolling(self.exit_days).min()
        avg_vol = vol.shift(1).rolling(self.entry_days).mean()

        w = pd.Series(0.0, index=prices.index)
        position = 0
        for i in range(len(prices)):
            if position == 0:
                if (
                    close.iloc[i] > prev_high.iloc[i]
                    and vol.iloc[i] > avg_vol.iloc[i]
                ):
                    position = 1
            else:
                if close.iloc[i] < prev_low.iloc[i]:
                    position = 0
            w.iloc[i] = position
        return pd.DataFrame({"QQQ": w}, index=prices.index)
