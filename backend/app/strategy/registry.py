from app.strategy.base import BaseStrategy
from app.strategy.samples.ma_regime_strategy import MovingAverageRegimeStrategy
from app.strategy.samples.mtf_trend_pullback_strategy import MTFTrendPullbackStrategy
from app.strategy.samples.trend_momentum_volume_score_v2 import TrendMomentumVolumeScoreV2Strategy


class StrategyRegistry:
    def __init__(self) -> None:
        self._strategies: dict[str, BaseStrategy] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        for strategy in (
            MovingAverageRegimeStrategy(),
            MTFTrendPullbackStrategy(),
            TrendMomentumVolumeScoreV2Strategy(),
        ):
            self._strategies[strategy.metadata().strategy_id] = strategy

    def list(self) -> list[BaseStrategy]:
        return list(self._strategies.values())

    def get(self, strategy_id: str) -> BaseStrategy:
        strategy = self._strategies.get(strategy_id)
        if strategy is None:
            raise KeyError(f"Unknown strategy_id: {strategy_id}")
        return strategy
