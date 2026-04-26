from datetime import datetime, timedelta

from app.models.candle import Candle
from app.strategy.base import StrategyContext
from app.strategy.samples.mtf_trend_pullback_v2_strategy import MTFTrendPullbackV2Strategy


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
                volume=volume + (i % 7) * 30,
            )
        )
    return rows


def _make_context(
    trend: list[Candle],
    setup: list[Candle],
    entry: list[Candle],
    runtime_state: dict | None = None,
) -> StrategyContext:
    return StrategyContext(
        symbol="KRW-ETH",
        timeframe_mapping={"trend": "1d", "setup": "60m", "entry": "15m"},
        candles_by_role={"trend": trend, "setup": setup, "entry": entry},
        metadata_by_role={"entry": {}, "setup": {}, "trend": {}},
        as_of=entry[-1].timestamp,
        entry_role="entry",
        runtime_state=runtime_state or {},
    )


def _base_context() -> StrategyContext:
    trend = _make_candles(260, datetime(2025, 1, 1), timedelta(days=1), drift=0.6, amplitude=1.2, volume=2000)
    setup = _make_candles(220, datetime(2025, 9, 1), timedelta(hours=1), drift=0.15, amplitude=0.8, volume=1200)
    entry = _make_candles(260, datetime(2025, 12, 1), timedelta(minutes=15), drift=0.06, amplitude=0.45, volume=900)

    # setup pullback near EMA20/EMA50 and still above EMA50
    for i in range(-8, 0):
        c = setup[i]
        setup[i] = Candle(
            timestamp=c.timestamp,
            open=c.open * 0.998,
            high=c.high * 1.001,
            low=c.low * 0.997,
            close=c.close * 0.997,
            volume=c.volume,
        )

    # entry reclaim + local high break + volume confirmation
    prev = entry[-2]
    last = entry[-1]
    entry[-2] = Candle(
        timestamp=prev.timestamp,
        open=prev.open * 0.997,
        high=prev.high * 0.999,
        low=prev.low * 0.995,
        close=prev.close * 0.996,
        volume=prev.volume,
    )
    entry[-1] = Candle(
        timestamp=last.timestamp,
        open=last.open * 1.001,
        high=last.high * 1.01,
        low=last.low * 1.0,
        close=max(last.close * 1.008, max(c.high for c in entry[-6:-1]) * 1.003),
        volume=last.volume * 1.4,
    )
    return _make_context(trend, setup, entry)


def test_trend_filter_rejects_when_not_bullish() -> None:
    strategy = MTFTrendPullbackV2Strategy()
    ctx = _base_context()
    trend = _make_candles(260, datetime(2025, 1, 1), timedelta(days=1), drift=-0.25, amplitude=1.0, volume=1800)
    bad_ctx = _make_context(trend, ctx.candles_by_role["setup"], ctx.candles_by_role["entry"])
    decision = strategy.evaluate_context(
        bad_ctx,
        strategy.default_params()
        | {
            "setup_rsi_min": 0.0,
            "setup_rsi_max": 100.0,
            "max_distance_from_60m_ema20_pct": 100.0,
            "max_atr_extension": 10.0,
        },
    )
    assert decision.entry_allowed is False
    assert decision.reject_reason in {"trend_not_bullish", "1d_trend_bearish"}


def test_setup_rsi_filter_rejects_out_of_range() -> None:
    strategy = MTFTrendPullbackV2Strategy()
    ctx = _base_context()
    setup = list(ctx.candles_by_role["setup"])
    # Push RSI too high.
    for i in range(-30, 0):
        c = setup[i]
        setup[i] = Candle(
            timestamp=c.timestamp,
            open=c.open * 1.01,
            high=c.high * 1.02,
            low=c.low * 1.005,
            close=c.close * 1.015,
            volume=c.volume,
        )
    bad_ctx = _make_context(ctx.candles_by_role["trend"], setup, ctx.candles_by_role["entry"])
    params = strategy.default_params() | {"setup_pullback_near_pct": 5.0}
    decision = strategy.evaluate_context(bad_ctx, params)
    assert decision.entry_allowed is False
    assert decision.reject_reason == "rsi_out_of_range"


def test_trigger_allows_entry_when_reclaim_or_high_break() -> None:
    strategy = MTFTrendPullbackV2Strategy()
    ctx = _base_context()
    params = strategy.default_params() | {
        "min_stop_pct": 0.2,
        "max_stop_pct": 6.0,
        "entry_volume_multiplier": 1.0,
        "max_distance_from_60m_ema20_pct": 6.0,
        "max_atr_extension": 10.0,
        "setup_rsi_min": 0.0,
        "setup_rsi_max": 100.0,
    }
    decision = strategy.evaluate_context(ctx, params)
    assert decision.entry_allowed is True
    assert decision.reject_reason is None


def test_chase_filter_blocks_overextended_entry() -> None:
    strategy = MTFTrendPullbackV2Strategy()
    ctx = _base_context()
    entry = list(ctx.candles_by_role["entry"])
    last = entry[-1]
    entry[-1] = Candle(
        timestamp=last.timestamp,
        open=last.open * 1.06,
        high=last.high * 1.09,
        low=last.low * 1.04,
        close=last.close * 1.08,
        volume=last.volume * 1.5,
    )
    bad_ctx = _make_context(ctx.candles_by_role["trend"], ctx.candles_by_role["setup"], entry)
    decision = strategy.evaluate_context(
        bad_ctx,
        strategy.default_params() | {"setup_rsi_min": 0.0, "setup_rsi_max": 100.0},
    )
    assert decision.entry_allowed is False
    assert decision.reject_reason == "chase_filter_blocked"


def test_stop_distance_bounds() -> None:
    strategy = MTFTrendPullbackV2Strategy()
    ctx = _base_context()

    too_tight = strategy.evaluate_context(
        ctx,
        strategy.default_params()
        | {
            "min_stop_pct": 2.5,
            "max_stop_pct": 6.0,
                "entry_volume_multiplier": 1.0,
                "setup_rsi_min": 0.0,
                "setup_rsi_max": 100.0,
                "max_distance_from_60m_ema20_pct": 100.0,
                "max_atr_extension": 10.0,
                "require_close_above_entry_ma": False,
                "require_local_high_break": False,
            },
        )
    assert too_tight.entry_allowed is False
    assert too_tight.reject_reason == "stop_too_tight"

    wide_ctx = _base_context()
    entry = list(wide_ctx.candles_by_role["entry"])
    for i in range(-30, 0):
        c = entry[i]
        entry[i] = Candle(
            timestamp=c.timestamp,
            open=c.open * 1.0,
            high=c.high * 1.12,
            low=c.low * 0.88,
            close=c.close * 1.0,
            volume=c.volume,
        )
    wider = _make_context(wide_ctx.candles_by_role["trend"], wide_ctx.candles_by_role["setup"], entry)
    too_wide = strategy.evaluate_context(
        wider,
        strategy.default_params()
        | {
            "min_stop_pct": 0.2,
            "max_stop_pct": 1.0,
                "entry_volume_multiplier": 1.0,
                "setup_rsi_min": 0.0,
                "setup_rsi_max": 100.0,
                "max_distance_from_60m_ema20_pct": 100.0,
                "max_atr_extension": 10.0,
                "require_close_above_entry_ma": False,
                "require_local_high_break": False,
            },
        )
    assert too_wide.entry_allowed is False
    assert too_wide.reject_reason == "risk_too_wide"


def test_cooldown_blocks_reentry_after_stop_loss() -> None:
    strategy = MTFTrendPullbackV2Strategy()
    ctx = _base_context()
    as_of = ctx.as_of
    runtime_state = {
        "last_exit_reason": "stop_loss",
        "last_exit_time": (as_of - timedelta(hours=2)).isoformat(),
        "consecutive_stop_losses": 1,
        "last_exit_was_profit": False,
    }
    cooldown_ctx = StrategyContext(
        symbol=ctx.symbol,
        timeframe_mapping=ctx.timeframe_mapping,
        candles_by_role=ctx.candles_by_role,
        metadata_by_role=ctx.metadata_by_role,
        as_of=ctx.as_of,
        entry_role="entry",
        runtime_state=runtime_state,
    )
    decision = strategy.evaluate_context(
        cooldown_ctx,
        strategy.default_params()
        | {
            "setup_rsi_min": 0.0,
            "setup_rsi_max": 100.0,
            "max_distance_from_60m_ema20_pct": 100.0,
            "max_atr_extension": 10.0,
        },
    )
    assert decision.entry_allowed is False
    assert decision.reject_reason == "cooldown_after_stop"
