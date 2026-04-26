from typing import Any

from app.strategy.base import StrategyMetadata
from app.strategy.samples.mtf_confluence_pullback_v2 import MTFConfluencePullbackV2Strategy


class BullAbove200LongV1LooserStrategy(MTFConfluencePullbackV2Strategy):
    """Bull-market-focused looser variant of mtf_confluence_pullback_v2."""

    def metadata(self) -> StrategyMetadata:
        return StrategyMetadata(
            strategy_id="bull_above_200_long_v1_looser",
            name="Bull Above 200 Long v1 (Looser)",
            version="1.0.0",
            description=(
                "Bull-market-only looser variant of mtf_confluence_pullback_v2. "
                "Keeps 1D MA200/EMA stack hard gate, while relaxing 4H trend, 1H setup, and 15M trigger filters."
            ),
            short_description=(
                "상승장(1D MA200 상방) 전용 완화형 MTF 전략. "
                "trend/setup/trigger 병목을 줄여 bull continuation 진입 기회를 확장."
            ),
            mode="multi_timeframe",
            required_roles=["regime", "trend", "setup", "trigger"],
            optional_roles=["confirmation", "execution"],
            spot_long_only=True,
        )

    def default_params(self) -> dict[str, Any]:
        p = super().default_params()
        p.update(
            {
                # Keep bull hard-gate; ease non-regime bottlenecks.
                "entry_score_threshold": 62.0,
                "allow_trend_alt_gate": True,
                "trend_structure_tolerance_pct": 1.2,
                "setup_rsi_min": 35.0,
                "setup_rsi_max": 68.0,
                "setup_pullback_near_pct": 2.4,
                "setup_lower_low_tolerance_pct": 0.7,
                "require_local_high_break": False,
                "allow_reclaim_bullish_without_high_break": True,
                "entry_volume_multiplier": 1.05,
                "trigger_bullish_body_ratio_min": 0.2,
            }
        )
        return p
