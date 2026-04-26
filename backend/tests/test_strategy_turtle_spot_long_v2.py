from datetime import datetime, timedelta

from app.models.candle import Candle
from app.strategy.base import StrategyContext
from app.strategy.samples.turtle_spot_long_v2 import TurtleSpotLongV2Strategy


def _candles(closes: list[float], minutes: int = 60, start: datetime | None = None) -> list[Candle]:
    base = start or datetime(2025, 1, 1)
    out: list[Candle] = []
    for i, close in enumerate(closes):
        out.append(
            Candle(
                timestamp=base + timedelta(minutes=minutes * i),
                open=close * 0.995,
                high=close * 1.01,
                low=close * 0.99,
                close=close,
                volume=1000 + i,
            )
        )
    return out


def _context(trend_closes: list[float], entry_closes: list[float], setup_closes: list[float] | None = None) -> StrategyContext:
    trend = _candles(trend_closes, minutes=24 * 60)
    entry = _candles(entry_closes, minutes=60)
    setup = _candles(setup_closes or entry_closes[-120:], minutes=240)
    return StrategyContext(
        symbol="KRW-BTC",
        timeframe_mapping={"trend": "1d", "setup": "240m", "entry": "60m"},
        candles_by_role={"trend": trend, "setup": setup, "entry": entry},
        metadata_by_role={},
        as_of=entry[-1].timestamp,
        entry_role="entry",
    )


def test_daily_ma200_filter_blocks_entry_when_below() -> None:
    strategy = TurtleSpotLongV2Strategy()
    trend = [220.0 for _ in range(230)] + [180.0 for _ in range(30)]
    entry = [100 + i * 0.2 for i in range(260)]
    entry[-1] = entry[-2] + 3.0

    decision = strategy.evaluate_context(_context(trend, entry), strategy.default_params())

    assert decision.entry_allowed is False
    assert decision.reject_reason == "daily_below_ma200"


def test_daily_ma200_slope_filter_blocks_entry_when_not_rising() -> None:
    strategy = TurtleSpotLongV2Strategy()
    # MA200 is declining, but latest close is still above MA200.
    trend = [190.0 for _ in range(40)] + [200.0 for _ in range(20)] + [189.0 for _ in range(180)] + [180.0 for _ in range(19)] + [191.0]
    entry = [100 + i * 0.2 for i in range(260)]
    entry[-1] = entry[-2] + 3.0

    decision = strategy.evaluate_context(_context(trend, entry), strategy.default_params())

    assert decision.entry_allowed is False
    assert decision.reject_reason == "daily_ma200_not_rising"


def test_breakout_entry_allowed_when_daily_gate_passes() -> None:
    strategy = TurtleSpotLongV2Strategy()
    trend = [100 + i * 0.5 for i in range(280)]
    entry = [120 + i * 0.15 for i in range(260)]
    entry[-1] = max(entry[-21:-1]) + 2.0

    decision = strategy.evaluate_context(_context(trend, entry), strategy.default_params())

    assert decision.entry_allowed is True
    assert decision.reject_reason is None
    assert decision.debug_info["is_breakout"] is True
    assert decision.debug_info["is_above_daily_ma200"] is True
    assert decision.debug_info["is_daily_ma200_rising"] is True


def test_atr_stop_loss_matches_multiple() -> None:
    strategy = TurtleSpotLongV2Strategy()
    trend = [100 + i * 0.4 for i in range(280)]
    entry = [120 + i * 0.2 for i in range(260)]
    entry[-1] = max(entry[-21:-1]) + 2.0

    decision = strategy.evaluate_context(_context(trend, entry), strategy.default_params())
    close_price = _context(trend, entry).candles_by_role["entry"][-1].close
    atr = decision.debug_info["atr_value"]
    expected = close_price - atr * 2.0

    assert decision.stop_loss is not None
    assert abs(decision.stop_loss - expected) < 1e-3


def test_exit_channel_breakdown_sets_bearish_regime() -> None:
    strategy = TurtleSpotLongV2Strategy()
    trend = [100 + i * 0.5 for i in range(280)]
    entry = [120 + i * 0.2 for i in range(259)]
    entry.append(min(entry[-10:]) - 2.5)

    decision = strategy.evaluate_context(_context(trend, entry), strategy.default_params())

    assert decision.regime == "bearish"
    assert decision.entry_allowed is False
    assert decision.reject_reason == "exit_channel_breakdown"
