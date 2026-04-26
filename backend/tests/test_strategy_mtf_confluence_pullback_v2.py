from datetime import datetime, timedelta

from app.models.candle import Candle
from app.strategy.base import StrategyContext
from app.strategy.samples.mtf_confluence_pullback_v2 import MTFConfluencePullbackV2Strategy


def _make_candles(
    count: int,
    start: datetime,
    step: timedelta,
    drift: float,
    amplitude: float = 1.0,
    volume: float = 1000.0,
) -> list[Candle]:
    rows: list[Candle] = []
    price = 100.0
    for i in range(count):
        price += drift
        swing = amplitude * (1.0 + (i % 5) * 0.15)
        rows.append(
            Candle(
                timestamp=start + i * step,
                open=price - swing * 0.25,
                high=price + swing * 0.55,
                low=price - swing * 0.55,
                close=price + swing * 0.2,
                volume=volume + (i % 7) * 35,
            )
        )
    return rows


def _base_context(runtime_state: dict | None = None) -> StrategyContext:
    regime = _make_candles(320, datetime(2024, 1, 1), timedelta(days=1), drift=0.7, amplitude=1.5, volume=2400)
    trend = _make_candles(320, datetime(2025, 1, 1), timedelta(hours=4), drift=0.3, amplitude=1.1, volume=1600)
    setup = _make_candles(320, datetime(2025, 6, 1), timedelta(hours=1), drift=0.08, amplitude=0.7, volume=1300)
    confirmation = _make_candles(320, datetime(2025, 10, 1), timedelta(minutes=30), drift=0.04, amplitude=0.5, volume=1000)
    trigger = _make_candles(320, datetime(2025, 12, 1), timedelta(minutes=15), drift=0.03, amplitude=0.35, volume=900)
    execution = _make_candles(320, datetime(2025, 12, 15), timedelta(minutes=5), drift=0.012, amplitude=0.2, volume=650)

    # setup: lightly pull back near EMA zone while preserving bullish context
    for i in range(-8, 0):
        c = setup[i]
        setup[i] = Candle(
            timestamp=c.timestamp,
            open=c.open * 0.998,
            high=c.high * 1.001,
            low=c.low * 0.997,
            close=c.close * 0.998,
            volume=c.volume,
        )

    # trigger: reclaim + local high break + volume confirmation
    prev = trigger[-2]
    last = trigger[-1]
    trigger[-2] = Candle(
        timestamp=prev.timestamp,
        open=prev.open * 0.996,
        high=prev.high * 0.999,
        low=prev.low * 0.995,
        close=prev.close * 0.997,
        volume=prev.volume,
    )
    trigger[-1] = Candle(
        timestamp=last.timestamp,
        open=last.open * 1.001,
        high=last.high * 1.008,
        low=last.low * 0.999,
        close=max(last.close * 1.006, max(c.high for c in trigger[-6:-1]) * 1.002),
        volume=last.volume * 1.4,
    )

    return StrategyContext(
        symbol="KRW-ETH",
        timeframe_mapping={
            "regime": "1d",
            "trend": "4h",
            "setup": "1h",
            "confirmation": "30m",
            "trigger": "15m",
            "execution": "5m",
        },
        candles_by_role={
            "regime": regime,
            "trend": trend,
            "setup": setup,
            "confirmation": confirmation,
            "trigger": trigger,
            "execution": execution,
        },
        metadata_by_role={},
        as_of=trigger[-1].timestamp,
        entry_role="trigger",
        runtime_state=runtime_state or {},
    )


def test_regime_filter_rejects_when_daily_below_ma200() -> None:
    strategy = MTFConfluencePullbackV2Strategy()
    ctx = _base_context()
    regime = _make_candles(320, datetime(2024, 1, 1), timedelta(days=1), drift=-0.45, amplitude=1.2, volume=2200)
    bad_ctx = StrategyContext(
        symbol=ctx.symbol,
        timeframe_mapping=ctx.timeframe_mapping,
        candles_by_role={**ctx.candles_by_role, "regime": regime},
        metadata_by_role=ctx.metadata_by_role,
        as_of=ctx.as_of,
        entry_role="trigger",
    )

    decision = strategy.evaluate_context(bad_ctx, strategy.default_params())
    assert decision.entry_allowed is False
    assert decision.reject_reason in {"regime_below_200_downtrend", "regime_recovery_not_confirmed"}


def test_regime_filter_rejects_when_ma200_not_rising() -> None:
    strategy = MTFConfluencePullbackV2Strategy()
    ctx = _base_context()
    regime = _make_candles(320, datetime(2024, 1, 1), timedelta(days=1), drift=0.0, amplitude=1.1, volume=2200)
    # force down-sloping long MA while keeping latest close relatively high
    for i in range(170, 319):
        c = regime[i]
        regime[i] = Candle(
            timestamp=c.timestamp,
            open=c.open * 0.985,
            high=c.high * 0.987,
            low=c.low * 0.98,
            close=c.close * 0.982,
            volume=c.volume,
        )
    last = regime[-1]
    regime[-1] = Candle(
        timestamp=last.timestamp,
        open=last.open * 1.03,
        high=last.high * 1.04,
        low=last.low * 1.02,
        close=last.close * 1.035,
        volume=last.volume,
    )
    bad_ctx = StrategyContext(
        symbol=ctx.symbol,
        timeframe_mapping=ctx.timeframe_mapping,
        candles_by_role={**ctx.candles_by_role, "regime": regime},
        metadata_by_role=ctx.metadata_by_role,
        as_of=ctx.as_of,
        entry_role="trigger",
    )

    decision = strategy.evaluate_context(bad_ctx, strategy.default_params())
    assert decision.entry_allowed is False
    assert decision.reject_reason in {"regime_above_200_but_weak", "regime_filter_blocked"}


def test_trend_filter_rejects_when_higher_timeframe_weak() -> None:
    strategy = MTFConfluencePullbackV2Strategy()
    ctx = _base_context()
    trend = _make_candles(320, datetime(2025, 1, 1), timedelta(hours=4), drift=-0.2, amplitude=1.0, volume=1500)
    bad_ctx = StrategyContext(
        symbol=ctx.symbol,
        timeframe_mapping=ctx.timeframe_mapping,
        candles_by_role={**ctx.candles_by_role, "trend": trend},
        metadata_by_role=ctx.metadata_by_role,
        as_of=ctx.as_of,
        entry_role="trigger",
    )

    decision = strategy.evaluate_context(
        bad_ctx,
        strategy.default_params() | {"setup_rsi_min": 0.0, "setup_rsi_max": 100.0, "setup_pullback_near_pct": 5.0},
    )
    assert decision.entry_allowed is False
    assert decision.reject_reason == "higher_timeframe_trend_weak"


def test_trigger_allows_entry_when_all_gates_pass() -> None:
    strategy = MTFConfluencePullbackV2Strategy()
    decision = strategy.evaluate_context(
        _base_context(),
        strategy.default_params()
        | {
            "setup_rsi_min": 0.0,
            "setup_rsi_max": 100.0,
            "setup_pullback_near_pct": 6.0,
            "entry_volume_multiplier": 1.0,
            "max_distance_from_setup_ema_pct": 25.0,
            "max_trigger_atr_extension": 10.0,
            "min_stop_pct": 0.2,
            "max_stop_pct": 8.0,
            "entry_score_threshold": 55.0,
        },
    )
    assert decision.entry_allowed is True
    assert decision.reject_reason is None
    assert decision.score >= 55.0


def test_execution_filter_blocks_overheated_5m() -> None:
    strategy = MTFConfluencePullbackV2Strategy()
    ctx = _base_context()
    execution = list(ctx.candles_by_role["execution"])
    last = execution[-1]
    execution[-1] = Candle(
        timestamp=last.timestamp,
        open=last.open * 1.03,
        high=last.high * 1.06,
        low=last.low * 1.02,
        close=last.close * 1.045,
        volume=last.volume * 2.0,
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
            "setup_pullback_near_pct": 6.0,
            "entry_volume_multiplier": 1.0,
            "max_distance_from_setup_ema_pct": 25.0,
            "max_trigger_atr_extension": 10.0,
            "min_stop_pct": 0.2,
            "max_stop_pct": 8.0,
            "entry_score_threshold": 55.0,
        },
    )
    assert decision.entry_allowed is False
    assert decision.reject_reason == "execution_overextended"


def test_stop_distance_bounds_reject_too_tight_and_too_wide() -> None:
    strategy = MTFConfluencePullbackV2Strategy()
    ctx = _base_context()

    tight = strategy.evaluate_context(
        ctx,
        strategy.default_params()
        | {
            "setup_rsi_min": 0.0,
            "setup_rsi_max": 100.0,
            "setup_pullback_near_pct": 6.0,
            "entry_volume_multiplier": 1.0,
            "max_distance_from_setup_ema_pct": 25.0,
            "max_trigger_atr_extension": 10.0,
            "min_stop_pct": 4.0,
            "max_stop_pct": 12.0,
            "entry_score_threshold": 55.0,
        },
    )
    assert tight.entry_allowed is False
    assert tight.reject_reason == "stop_too_tight"

    wide = strategy.evaluate_context(
        ctx,
        strategy.default_params()
        | {
            "setup_rsi_min": 0.0,
            "setup_rsi_max": 100.0,
            "setup_pullback_near_pct": 6.0,
            "entry_volume_multiplier": 1.0,
            "max_distance_from_setup_ema_pct": 25.0,
            "max_trigger_atr_extension": 10.0,
            "min_stop_pct": 0.1,
            "max_stop_pct": 0.4,
            "entry_score_threshold": 55.0,
        },
    )
    assert wide.entry_allowed is False
    assert wide.reject_reason == "risk_too_wide"


def test_cooldown_blocks_reentry_after_stop_loss() -> None:
    strategy = MTFConfluencePullbackV2Strategy()
    ctx = _base_context(
        runtime_state={
            "last_exit_reason": "stop_loss",
            "last_exit_time": (datetime(2026, 1, 1, 0, 0) - timedelta(hours=2)).isoformat(),
            "consecutive_stop_losses": 1,
            "last_exit_was_profit": False,
        }
    )
    cooldown_ctx = StrategyContext(
        symbol=ctx.symbol,
        timeframe_mapping=ctx.timeframe_mapping,
        candles_by_role=ctx.candles_by_role,
        metadata_by_role=ctx.metadata_by_role,
        as_of=datetime(2026, 1, 1, 0, 0),
        entry_role="trigger",
        runtime_state=ctx.runtime_state,
    )

    decision = strategy.evaluate_context(
        cooldown_ctx,
        strategy.default_params()
        | {
            "setup_rsi_min": 0.0,
            "setup_rsi_max": 100.0,
            "setup_pullback_near_pct": 6.0,
            "entry_volume_multiplier": 1.0,
            "max_distance_from_setup_ema_pct": 25.0,
            "max_trigger_atr_extension": 10.0,
            "min_stop_pct": 0.2,
            "max_stop_pct": 8.0,
            "entry_score_threshold": 55.0,
        },
    )
    assert decision.entry_allowed is False
    assert decision.reject_reason == "cooldown_after_stop"
