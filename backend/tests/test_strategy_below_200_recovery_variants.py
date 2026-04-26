from __future__ import annotations

from app.models.candle import Candle
from app.strategy.base import StrategyContext
from app.strategy.registry import StrategyRegistry
from app.strategy.samples.below_200_recovery_long_v1_variants import (
    Below200RecoveryLongV1LooserRegimeStrategy,
    Below200RecoveryLongV1LooserSetupStrategy,
    Below200RecoveryLongV1LooserTriggerStrategy,
)
from test_strategy_below_200_recovery_long_v1 import _base_context


def test_registry_contains_new_recovery_variants() -> None:
    ids = {s.metadata().strategy_id for s in StrategyRegistry().list()}
    assert "below_200_recovery_long_v1_looser_setup" in ids
    assert "below_200_recovery_long_v1_looser_trigger" in ids


def test_strategies_api_exposes_new_recovery_variants(api_client) -> None:
    response = api_client.get("/strategies")
    assert response.status_code == 200
    ids = {item["strategy_id"] for item in response.json()}
    assert "below_200_recovery_long_v1_looser_setup" in ids
    assert "below_200_recovery_long_v1_looser_trigger" in ids


def test_looser_setup_reduces_setup_pullback_rejects() -> None:
    base = Below200RecoveryLongV1LooserRegimeStrategy()
    variant = Below200RecoveryLongV1LooserSetupStrategy()
    ctx = _base_context()

    setup = list(ctx.candles_by_role["setup"])
    ema20 = base._ema(setup, 20)[-1]  # type: ignore[attr-defined]
    adjusted_close = ema20 * 1.015  # outside 1.2% but inside 2.0% band
    last = setup[-1]
    setup[-1] = Candle(
        timestamp=last.timestamp,
        open=adjusted_close * 0.999,
        high=adjusted_close * 1.003,
        low=adjusted_close * 0.997,
        close=adjusted_close,
        volume=last.volume,
    )
    mod_ctx = StrategyContext(
        symbol=ctx.symbol,
        timeframe_mapping=ctx.timeframe_mapping,
        candles_by_role={**ctx.candles_by_role, "setup": setup},
        metadata_by_role=ctx.metadata_by_role,
        as_of=ctx.as_of,
        entry_role="trigger",
        runtime_state=ctx.runtime_state,
    )

    common_overrides = {
        "max_distance_below_sma200_pct": 50.0,
        "require_daily_ema20_recovery": False,
        "setup_rsi_min": 0.0,
        "setup_rsi_max": 100.0,
        "reject_lower_low": False,
        "trigger_volume_multiplier": 1.0,
        "entry_score_threshold": 55.0,
        "min_stop_pct": 0.2,
        "max_stop_pct": 8.0,
    }

    base_decision = base.evaluate_context(mod_ctx, base.default_params() | common_overrides)
    variant_decision = variant.evaluate_context(mod_ctx, variant.default_params() | common_overrides)

    assert base_decision.reject_reason == "setup_not_pullback"
    assert variant_decision.reject_reason != "setup_not_pullback"


def test_looser_trigger_reduces_local_high_or_volume_rejects() -> None:
    base = Below200RecoveryLongV1LooserRegimeStrategy()
    variant = Below200RecoveryLongV1LooserTriggerStrategy()
    ctx = _base_context()

    trigger = list(ctx.candles_by_role["trigger"])
    prev_local_high = max(c.high for c in trigger[-6:-1])
    last = trigger[-1]
    # Reclaim above EMA20 but still below local high; volume near SMA20.
    trigger[-1] = Candle(
        timestamp=last.timestamp,
        open=last.open,
        high=min(last.high, prev_local_high * 0.999),
        low=last.low,
        close=min(last.close, prev_local_high * 0.998),
        volume=last.volume * 1.02,
    )

    mod_ctx = StrategyContext(
        symbol=ctx.symbol,
        timeframe_mapping=ctx.timeframe_mapping,
        candles_by_role={**ctx.candles_by_role, "trigger": trigger},
        metadata_by_role=ctx.metadata_by_role,
        as_of=ctx.as_of,
        entry_role="trigger",
        runtime_state=ctx.runtime_state,
    )

    common_overrides = {
        "max_distance_below_sma200_pct": 50.0,
        "require_daily_ema20_recovery": False,
        "setup_rsi_min": 0.0,
        "setup_rsi_max": 100.0,
        "setup_pullback_near_pct": 8.0,
        "min_stop_pct": 0.2,
        "max_stop_pct": 8.0,
        "entry_score_threshold": 55.0,
    }

    base_decision = base.evaluate_context(mod_ctx, base.default_params() | common_overrides)
    variant_decision = variant.evaluate_context(mod_ctx, variant.default_params() | common_overrides)

    assert base_decision.reject_reason in {"no_local_high_break", "trigger_volume_not_confirmed"}
    assert variant_decision.reject_reason not in {"no_local_high_break", "trigger_volume_not_confirmed"}
