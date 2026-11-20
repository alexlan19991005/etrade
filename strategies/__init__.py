"""Strategy registry — import all strategies here."""

from .base import BaseStrategy
from .trend_ma import TrendMAStrategy
from .momentum_rotation import MomentumRotationStrategy, UNIVERSE
from .mean_reversion_rsi import MeanReversionRSIStrategy
from .breakout_donchian import BreakoutDonchianStrategy
from .defensive_rotation import DefensiveRotationStrategy

ALL_STRATEGIES = [
    TrendMAStrategy,
    MomentumRotationStrategy,
    MeanReversionRSIStrategy,
    BreakoutDonchianStrategy,
    DefensiveRotationStrategy,
]

__all__ = [
    "BaseStrategy",
    "TrendMAStrategy",
    "MomentumRotationStrategy",
    "MeanReversionRSIStrategy",
    "BreakoutDonchianStrategy",
    "DefensiveRotationStrategy",
    "UNIVERSE",
    "ALL_STRATEGIES",
]
