from datetime import datetime, timedelta

from app.models.candle import Candle
from app.strategy.base import StrategyContext
from app.strategy.samples.below_200_recovery_long_v1 import Below200RecoveryLongV1Strategy


def _make_candles(
    count: int,
    start: datetime,
    step: timedelta,
    base: float,
    drift: float,
    amplitude: float = 1.0,
    volume: float = 1000.0,
) -> list[Candle]:
    rows: list[Candle] = []
    price = base
    for i in range(count):
        price += drift
        wiggle = amplitude * (1 + (i % 4) * 0.1)
        rows.append(
            Candle(
                timestamp=start + i * step,
                open=price - wiggle * 0.2,
                high=price + wiggle * 0.5,
                low=price - wiggle * 0.5,
                close=price + wiggle * 0.1,
                volume=volume + (i % 6) * 20,
            )
        )
    return rows


def _regime_recovery_candles() -> list[Candle]:
    start = datetime(2024, 1, 1)
    # High plateau -> sharp drawdown -> recovery bounce.
    # Last close remains below SMA200, but EMA stack / momentum indicates recovery regime.
    closes: list[float] = []
    closes += [260 - i * 0.05 for i in range(220)]
    closes += [249 - i * 1.4 for i in range(80)]
    closes += [137 + i * 0.7 for i in range(40)]
    rows: list[Candle] = []
    for i, close in enumerate(closes):
        rows.append(
            Candle(
                timestamp=start + i * timedelta(days=1),
                open=close * 0.998,
                high=close * 1.005,
                low=close * 0.995,
                close=close,
                volume=2200 + (i % 5) * 30,
            )
        )
    return rows


def _base_context(runtime_state: dict | None = None) -> StrategyContext:
    regime = _regime_recovery_candles()
    trend = _make_candles(340, datetime(2025, 5, 1), timedelta(hours=4), base=100, drift=0.08, amplitude=0.9, volume=1600)
    setup = _make_candles(340, datetime(2025, 9, 1), timedelta(hours=1), base=100, drift=0.02, amplitude=0.7, volume=1200)
    trigger = _make_candles(340, datetime(2025, 12, 1), timedelta(minutes=15), base=100, drift=0.01, amplitude=0.35, volume=900)
    execution = _make_candles(340, datetime(2025, 12, 25), timedelta(minutes=5), base=100, drift=0.004, amplitude=0.2, volume=650)

    # setup near EMA and non-breaking low
    for i in range(-10, 0):
        c = setup[i]
        setup[i] = Candle(
            timestamp=c.timestamp,
            open=c.open * 0.999,
            high=c.high * 1.001,
            low=c.low * 0.998,
            close=c.close * 0.999,
            volume=c.volume,
        )

    # trigger reclaim + local high break + volume surge
    prev = trigger[-2]
    last = trigger[-1]
    trigger[-2] = Candle(
        timestamp=prev.timestamp,
        open=prev.open * 0.996,
        high=prev.high * 0.998,
        low=prev.low * 0.995,
        close=prev.close * 0.996,
        volume=prev.volume,
    )
    trigger[-1] = Candle(
        timestamp=last.timestamp,
        open=last.open * 1.002,
        high=max(last.high * 1.01, max(c.high for c in trigger[-6:-1]) * 1.003),
        low=last.low * 1.0,
        close=max(last.close * 1.008, max(c.high for c in trigger[-6:-1]) * 1.002),
        volume=last.volume * 1.5,
    )

    return StrategyContext(
        symbol="KRW-ETH",
        timeframe_mapping={
            "regime": "1d",
            "trend": "4h",
            "setup": "1h",
            "trigger": "15m",
            "execution": "5m",
        },
        candles_by_role={
            "regime": regime,
            "trend": trend,
            "setup": setup,
            "trigger": trigger,
            "execution": execution,
        },
        metadata_by_role={},
        as_of=trigger[-1].timestamp,
        entry_role="trigger",
        runtime_state=runtime_state or {},
    )


def test_regime_gate_rejects_non_recovery() -> None:
    strategy = Below200RecoveryLongV1Strategy()
    ctx = _base_context()
    bad_regime = _make_candles(360, datetime(2024, 1, 1), timedelta(days=1), base=120, drift=-0.4, amplitude=1.2, volume=2200)
    bad_ctx = StrategyContext(
        symbol=ctx.symbol,
        timeframe_mapping=ctx.timeframe_mapping,
        candles_by_role={**ctx.candles_by_role, "regime": bad_regime},
        metadata_by_role=ctx.metadata_by_role,
        as_of=ctx.as_of,
        entry_role="trigger",
    )
    decision = strategy.evaluate_context(bad_ctx, strategy.default_params() | {"max_distance_below_sma200_pct": 50.0})
    assert decision.entry_allowed is False
    assert decision.reject_reason == "not_below_200_recovery"


def test_distance_filter_rejects_too_far_below_sma200() -> None:
    strategy = Below200RecoveryLongV1Strategy()
    decision = strategy.evaluate_context(
        _base_context(),
        strategy.default_params() | {"max_distance_below_sma200_pct": 1.0},
    )
    assert decision.entry_allowed is False
    assert decision.reject_reason == "too_far_below_sma200"


def test_higher_low_filter_rejects_missing_structure() -> None:
    strategy = Below200RecoveryLongV1Strategy()
    ctx = _base_context()
    bad_trend = _make_candles(340, datetime(2025, 5, 1), timedelta(hours=4), base=120, drift=-0.1, amplitude=0.8, volume=1600)
    bad_ctx = StrategyContext(
        symbol=ctx.symbol,
        timeframe_mapping=ctx.timeframe_mapping,
        candles_by_role={**ctx.candles_by_role, "trend": bad_trend},
        metadata_by_role=ctx.metadata_by_role,
        as_of=ctx.as_of,
        entry_role="trigger",
    )
    decision = strategy.evaluate_context(bad_ctx, strategy.default_params() | {"max_distance_below_sma200_pct": 50.0})
    assert decision.entry_allowed is False
    assert decision.reject_reason in {"trend_higher_low_missing", "trend_below_ema20", "recovery_structure_not_ready"}


def test_setup_filter_rejects_when_not_pullback() -> None:
    strategy = Below200RecoveryLongV1Strategy()
    ctx = _base_context()
    setup = list(ctx.candles_by_role["setup"])
    for i in range(-12, 0):
        c = setup[i]
        setup[i] = Candle(
            timestamp=c.timestamp,
            open=c.open * 1.08,
            high=c.high * 1.09,
            low=c.low * 1.07,
            close=c.close * 1.08,
            volume=c.volume,
        )
    bad_ctx = StrategyContext(
        symbol=ctx.symbol,
        timeframe_mapping=ctx.timeframe_mapping,
        candles_by_role={**ctx.candles_by_role, "setup": setup},
        metadata_by_role=ctx.metadata_by_role,
        as_of=ctx.as_of,
        entry_role="trigger",
    )
    decision = strategy.evaluate_context(bad_ctx, strategy.default_params() | {"max_distance_below_sma200_pct": 50.0})
    assert decision.entry_allowed is False
    assert decision.reject_reason == "setup_not_pullback"


def test_trigger_can_allow_entry() -> None:
    strategy = Below200RecoveryLongV1Strategy()
    decision = strategy.evaluate_context(
        _base_context(),
        strategy.default_params()
        | {
            "setup_rsi_min": 0.0,
            "setup_rsi_max": 100.0,
            "setup_pullback_near_pct": 8.0,
            "trigger_volume_multiplier": 1.0,
            "min_stop_pct": 0.2,
            "max_stop_pct": 8.0,
            "entry_score_threshold": 60.0,
                "max_distance_below_sma200_pct": 50.0,
            "require_daily_ema20_recovery": False,
        },
    )
    assert decision.entry_allowed is True
    assert decision.reject_reason is None


def test_execution_filter_rejects_overheated_5m() -> None:
    strategy = Below200RecoveryLongV1Strategy()
    ctx = _base_context()
    execution = list(ctx.candles_by_role["execution"])
    last = execution[-1]
    execution[-1] = Candle(
        timestamp=last.timestamp,
        open=last.open * 1.03,
        high=last.high * 1.06,
        low=last.low * 1.02,
        close=last.close * 1.045,
        volume=last.volume * 2,
    )
    bad_ctx = StrategyContext(
        symbol=ctx.symbol,
        timeframe_mapping=ctx.timeframe_mapping,
        candles_by_role={**ctx.candles_by_role, "execution": execution},
        metadata_by_role=ctx.metadata_by_role,
        as_of=ctx.as_of,
        entry_role="trigger",
    )
    decision = strategy.evaluate_context(
        bad_ctx,
        strategy.default_params()
        | {
            "setup_rsi_min": 0.0,
            "setup_rsi_max": 100.0,
            "setup_pullback_near_pct": 8.0,
            "trigger_volume_multiplier": 1.0,
            "min_stop_pct": 0.2,
            "max_stop_pct": 8.0,
            "entry_score_threshold": 60.0,
                "max_distance_below_sma200_pct": 50.0,
            "require_daily_ema20_recovery": False,
        },
    )
    assert decision.entry_allowed is False
    assert decision.reject_reason == "execution_overextended"


def test_stop_distance_bounds() -> None:
    strategy = Below200RecoveryLongV1Strategy()
    ctx = _base_context()

    tight = strategy.evaluate_context(
        ctx,
        strategy.default_params()
        | {
            "min_stop_pct": 4.0,
            "max_stop_pct": 10.0,
            "max_distance_below_sma200_pct": 50.0,
            "setup_rsi_min": 0.0,
            "setup_rsi_max": 100.0,
            "setup_pullback_near_pct": 8.0,
            "trigger_volume_multiplier": 1.0,
            "require_daily_ema20_recovery": False,
        },
    )
    assert tight.entry_allowed is False
    assert tight.reject_reason == "stop_too_tight"

    wide = strategy.evaluate_context(
        ctx,
        strategy.default_params()
        | {
            "min_stop_pct": 0.1,
            "max_stop_pct": 0.4,
            "max_distance_below_sma200_pct": 50.0,
            "setup_rsi_min": 0.0,
            "setup_rsi_max": 100.0,
            "setup_pullback_near_pct": 8.0,
            "trigger_volume_multiplier": 1.0,
            "require_daily_ema20_recovery": False,
        },
    )
    assert wide.entry_allowed is False
    assert wide.reject_reason == "risk_too_wide"


def test_cooldown_blocks_reentry_after_stop_loss() -> None:
    strategy = Below200RecoveryLongV1Strategy()
    now = datetime(2026, 1, 1, 12, 0)
    ctx = _base_context(
        runtime_state={
            "last_exit_reason": "stop_loss",
            "last_exit_time": (now - timedelta(hours=3)).isoformat(),
            "consecutive_stop_losses": 1,
            "last_exit_was_profit": False,
        }
    )
    cooldown_ctx = StrategyContext(
        symbol=ctx.symbol,
        timeframe_mapping=ctx.timeframe_mapping,
        candles_by_role=ctx.candles_by_role,
        metadata_by_role=ctx.metadata_by_role,
        as_of=now,
        entry_role="trigger",
        runtime_state=ctx.runtime_state,
    )
    decision = strategy.evaluate_context(
        cooldown_ctx,
        strategy.default_params()
        | {
            "max_distance_below_sma200_pct": 50.0,
            "require_daily_ema20_recovery": False,
            "setup_rsi_min": 0.0,
            "setup_rsi_max": 100.0,
            "setup_pullback_near_pct": 8.0,
            "trigger_volume_multiplier": 1.0,
            "min_stop_pct": 0.2,
            "max_stop_pct": 8.0,
            "entry_score_threshold": 60.0,
        },
    )
    assert decision.entry_allowed is False
    assert decision.reject_reason == "cooldown_after_stop"
