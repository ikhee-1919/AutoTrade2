from typing import Any

from app.strategy.base import StrategyMetadata
from app.strategy.samples.below_200_recovery_long_v1 import Below200RecoveryLongV1Strategy


class Below200RecoveryLongV1Distance18Strategy(Below200RecoveryLongV1Strategy):
    """Variant: relax only the below-SMA200 distance gate."""

    def metadata(self) -> StrategyMetadata:
        return StrategyMetadata(
            strategy_id="below_200_recovery_long_v1_distance18",
            name="Below 200 Recovery Long v1 (Distance 18)",
            version="1.0.0-distance18",
            description=(
                "Recovery long variant that primarily relaxes max distance below SMA200 to 18%."
            ),
            short_description=(
                "below_200_recovery_long_v1 대비 SMA200 하방 거리 제한만 18%로 완화한 variant"
            ),
            mode="multi_timeframe",
            required_roles=["regime", "trend", "setup", "trigger"],
            optional_roles=["execution"],
            spot_long_only=True,
        )

    def default_params(self) -> dict[str, Any]:
        p = super().default_params()
        p["max_distance_below_sma200_pct"] = 18.0
        return p


class Below200RecoveryLongV1LooserRegimeStrategy(Below200RecoveryLongV1Strategy):
    """Variant: relax recovery regime gates while still avoiding below_200_downtrend."""

    def metadata(self) -> StrategyMetadata:
        return StrategyMetadata(
            strategy_id="below_200_recovery_long_v1_looser_regime",
            name="Below 200 Recovery Long v1 (Looser Regime)",
            version="1.0.0-looser-regime",
            description=(
                "Recovery long variant with looser recovery-regime gating. "
                "Base strategy: below_200_recovery_long_v1."
            ),
            short_description=(
                "recovery 판정을 완화(EMA20 회복 필수 해제, 4H higher-low 완화)한 variant"
            ),
            mode="multi_timeframe",
            required_roles=["regime", "trend", "setup", "trigger"],
            optional_roles=["execution"],
            spot_long_only=True,
        )

    def default_params(self) -> dict[str, Any]:
        p = super().default_params()
        p.update(
            {
                "max_distance_below_sma200_pct": 18.0,
                "require_daily_ema20_recovery": False,
                "require_higher_low": False,
                "require_4h_close_above_ema20": True,
                "entry_score_threshold": 62.0,
            }
        )
        return p


class Below200RecoveryLongV1LooserSetupStrategy(Below200RecoveryLongV1LooserRegimeStrategy):
    """Variant: keep looser regime baseline, relax setup bottlenecks."""

    def metadata(self) -> StrategyMetadata:
        return StrategyMetadata(
            strategy_id="below_200_recovery_long_v1_looser_setup",
            name="Below 200 Recovery Long v1 (Looser Setup)",
            version="1.0.0-looser-setup",
            description=(
                "Setup-relaxed variant on top of below_200_recovery_long_v1_looser_regime. "
                "Focuses on reducing setup-stage rejects."
            ),
            short_description=(
                "base=looser_regime / setup RSI 범위·EMA 근접·lower-low 판정을 완화한 setup 병목 해소 variant"
            ),
            mode="multi_timeframe",
            required_roles=["regime", "trend", "setup", "trigger"],
            optional_roles=["execution"],
            spot_long_only=True,
        )

    def default_params(self) -> dict[str, Any]:
        p = super().default_params()
        p.update(
            {
                "setup_rsi_min": 38.0,
                "setup_rsi_max": 68.0,
                "setup_pullback_near_pct": 2.0,
                "reject_lower_low": False,
                "entry_score_threshold": 60.0,
            }
        )
        return p


class Below200RecoveryLongV1LooserTriggerStrategy(Below200RecoveryLongV1LooserRegimeStrategy):
    """Variant: keep looser regime baseline, relax trigger bottlenecks."""

    def metadata(self) -> StrategyMetadata:
        return StrategyMetadata(
            strategy_id="below_200_recovery_long_v1_looser_trigger",
            name="Below 200 Recovery Long v1 (Looser Trigger)",
            version="1.0.0-looser-trigger",
            description=(
                "Trigger-relaxed variant on top of below_200_recovery_long_v1_looser_regime. "
                "Focuses on reducing trigger-stage rejects."
            ),
            short_description=(
                "base=looser_regime / local-high·volume·reclaim 조건을 완화한 trigger 병목 해소 variant"
            ),
            mode="multi_timeframe",
            required_roles=["regime", "trend", "setup", "trigger"],
            optional_roles=["execution"],
            spot_long_only=True,
        )

    def default_params(self) -> dict[str, Any]:
        p = super().default_params()
        p.update(
            {
                "require_local_high_break": False,
                "trigger_volume_multiplier": 1.0,
                "entry_score_threshold": 58.0,
            }
        )
        return p


class Below200RecoveryLongV1MediumStrategy(Below200RecoveryLongV1Strategy):
    """Variant: medium relaxation between baseline and looser_regime."""

    def metadata(self) -> StrategyMetadata:
        return StrategyMetadata(
            strategy_id="below_200_recovery_long_v1_medium",
            name="Below 200 Recovery Long v1 (Medium)",
            version="1.0.0-medium",
            description=(
                "Recovery long variant with mild regime/setup relaxations."
            ),
            short_description=(
                "regime 완화는 제한적으로, setup/trigger 조건을 소폭 완화한 중간 강도 variant"
            ),
            mode="multi_timeframe",
            required_roles=["regime", "trend", "setup", "trigger"],
            optional_roles=["execution"],
            spot_long_only=True,
        )

    def default_params(self) -> dict[str, Any]:
        p = super().default_params()
        p.update(
            {
                "max_distance_below_sma200_pct": 15.0,
                "setup_rsi_min": 40.0,
                "setup_rsi_max": 64.0,
                "setup_pullback_near_pct": 1.6,
                "trigger_volume_multiplier": 1.05,
                "entry_score_threshold": 66.0,
            }
        )
        return p
