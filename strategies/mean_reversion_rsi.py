"""RSI mean reversion on SPY (short-term).

Buy SPY when 14-day RSI drops below 30; exit when RSI rises above 70 or
after 10 days. Wins on sharp, short-lived dips in a healthy market; loses
in real bear markets, where RSI can sit below 30 for weeks while prices
keep falling — the 10-day cap is the main protection.

Parameters: rsi_period=14 (Wilder's smoothing), buy_below=30,
sell_above=70, max_hold_days=10.
"""

import pandas as pd

from .base import BaseStrategy


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Wilder's RSI; uses closes up to each day only."""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - 100 / (1 + rs)


class MeanReversionRSIStrategy(BaseStrategy):
    name = "mean_reversion_rsi"
    symbols = ["SPY"]

    def __init__(
        self,
        rsi_period: int = 14,
        buy_below: float = 30.0,
        sell_above: float = 70.0,
        max_hold_days: int = 10,
    ):
        self.rsi_period = rsi_period
        self.buy_below = buy_below
        self.sell_above = sell_above
        self.max_hold_days = max_hold_days

    def generate_signals(
        self, prices: pd.DataFrame, data: dict | None = None
    ) -> pd.DataFrame:
        rsi = _rsi(prices["SPY"], self.rsi_period)
        w = pd.Series(0.0, index=prices.index)
        position = 0
        hold_days = 0
        for i in range(len(prices)):
            if position == 0:
                if rsi.iloc[i] < self.buy_below:
                    position = 1
                    hold_days = 0
            else:
                hold_days += 1
                if (
                    rsi.iloc[i] > self.sell_above
                    or hold_days >= self.max_hold_days
                ):
                    position = 0
            w.iloc[i] = position
        return pd.DataFrame({"SPY": w}, index=prices.index)
