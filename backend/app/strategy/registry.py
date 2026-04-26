from app.strategy.base import BaseStrategy
from app.strategy.samples.below_200_recovery_long_v1 import Below200RecoveryLongV1Strategy
from app.strategy.samples.below_200_recovery_long_v1_variants import (
    Below200RecoveryLongV1Distance18Strategy,
    Below200RecoveryLongV1LooserSetupStrategy,
    Below200RecoveryLongV1LooserTriggerStrategy,
    Below200RecoveryLongV1LooserRegimeStrategy,
    Below200RecoveryLongV1MediumStrategy,
)
from app.strategy.samples.ma_regime_strategy import MovingAverageRegimeStrategy
from app.strategy.samples.mtf_confluence_pullback_v2 import MTFConfluencePullbackV2Strategy
from app.strategy.samples.mtf_confluence_pullback_v2_variants import BullAbove200LongV1LooserStrategy
from app.strategy.samples.mtf_trend_pullback_strategy import MTFTrendPullbackStrategy
from app.strategy.samples.mtf_trend_pullback_v2_strategy import MTFTrendPullbackV2Strategy
from app.strategy.samples.turtle_breakout_strategy import TurtleBreakoutStrategy
from app.strategy.samples.turtle_spot_long_v2 import TurtleSpotLongV2Strategy
from app.strategy.samples.trend_momentum_volume_score_v2 import TrendMomentumVolumeScoreV2Strategy


class StrategyRegistry:
    def __init__(self) -> None:
        self._strategies: dict[str, BaseStrategy] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        for strategy in (
            MovingAverageRegimeStrategy(),
            MTFTrendPullbackStrategy(),
            MTFTrendPullbackV2Strategy(),
            MTFConfluencePullbackV2Strategy(),
            BullAbove200LongV1LooserStrategy(),
            Below200RecoveryLongV1Strategy(),
            Below200RecoveryLongV1Distance18Strategy(),
            Below200RecoveryLongV1LooserRegimeStrategy(),
            Below200RecoveryLongV1LooserSetupStrategy(),
            Below200RecoveryLongV1LooserTriggerStrategy(),
            Below200RecoveryLongV1MediumStrategy(),
            TrendMomentumVolumeScoreV2Strategy(),
            TurtleBreakoutStrategy(),
            TurtleSpotLongV2Strategy(),
        ):
            self._strategies[strategy.metadata().strategy_id] = strategy

    def list(self) -> list[BaseStrategy]:
        return list(self._strategies.values())

    def get(self, strategy_id: str) -> BaseStrategy:
        strategy = self._strategies.get(strategy_id)
        if strategy is None:
            raise KeyError(f"Unknown strategy_id: {strategy_id}")
        return strategy
