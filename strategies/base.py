"""Common interface for all strategies.

Every strategy is a class with:

    name: str
    symbols: list[str]          # symbols the strategy may hold
    generate_signals(prices, data=None) -> pd.DataFrame
        prices: DataFrame of daily closes, columns = symbols, index = dates.
                Only past data up to row ``t`` is used to compute the signal
                at ``t`` (all indicators use rolling windows / shifts that
                never peek at future rows).
        data: optional dict with 'open'/'high'/'low'/'volume' DataFrames
              (same shape as prices) for strategies that need more than
              closes (e.g. Donchian breakout needs highs/lows/volume).
        returns: DataFrame of target weights (same index; columns are a
                 subset of ``symbols``), rows sum to <= 1. The engine
                 executes a signal computed from closes at day ``t`` at the
                 open of day ``t+1``, so no lookahead is possible.
"""

from abc import ABC, abstractmethod

import pandas as pd


class BaseStrategy(ABC):
    name: str = "base"
    symbols: list = []

    @abstractmethod
    def generate_signals(
        self, prices: pd.DataFrame, data: dict | None = None
    ) -> pd.DataFrame:
        raise NotImplementedError
