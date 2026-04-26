from datetime import datetime, timedelta

from app.models.candle import Candle
from app.strategy.samples.turtle_breakout_strategy import TurtleBreakoutStrategy


def _candles_from_closes(closes: list[float], start: datetime | None = None) -> list[Candle]:
    base = start or datetime(2025, 1, 1)
    rows: list[Candle] = []
    for i, close in enumerate(closes):
        rows.append(
            Candle(
                timestamp=base + timedelta(days=i),
                open=close * 0.995,
                high=close * 1.01,
                low=close * 0.99,
                close=close,
                volume=1000 + i,
            )
        )
    return rows


def test_breakout_entry_allowed_when_close_breaks_channel() -> None:
    strategy = TurtleBreakoutStrategy()
    closes = [100 + i * 0.4 for i in range(260)]
    # Force a clear close breakout over recent 20 highs.
    closes[-1] = closes[-2] + 5.0
    candles = _candles_from_closes(closes)

    decision = strategy.evaluate(candles, strategy.default_params())

    assert decision.entry_allowed is True
    assert decision.reject_reason is None
    assert decision.debug_info["is_breakout"] is True


def test_trend_filter_blocks_entry_when_below_ma200() -> None:
    strategy = TurtleBreakoutStrategy()
    # High historical prices keep MA200 high, recent 20-day breakout can still happen below MA200.
    closes = [210.0 for _ in range(220)] + [100 + i * 0.3 for i in range(39)]
    closes.append(125.0)
    candles = _candles_from_closes(closes)

    decision = strategy.evaluate(candles, strategy.default_params())

    assert decision.entry_allowed is False
    assert decision.reject_reason == "trend_filter_blocked"
    assert decision.debug_info["is_breakout"] is True
    assert decision.debug_info["is_above_trend_ma"] is False


def test_atr_stop_loss_matches_atr_multiple() -> None:
    strategy = TurtleBreakoutStrategy()
    candles = _candles_from_closes([100 + i * 0.35 for i in range(260)])

    params = strategy.default_params() | {"atr_stop_multiple": 2.0, "atr_length": 20}
    decision = strategy.evaluate(candles, params)

    close_price = decision.debug_info["close_price"]
    atr_value = decision.debug_info["atr_value"]
    expected_stop = close_price - atr_value * 2.0
    assert decision.stop_loss is not None
    assert abs(decision.stop_loss - expected_stop) < 1e-4


def test_exit_channel_breakdown_sets_bearish_regime() -> None:
    strategy = TurtleBreakoutStrategy()
    closes = [120 + i * 0.25 for i in range(259)]
    # Final close breaks below recent 10-bar lows.
    closes.append(min(closes[-10:]) - 3.0)
    candles = _candles_from_closes(closes)

    decision = strategy.evaluate(candles, strategy.default_params())

    assert decision.regime == "bearish"
    assert decision.entry_allowed is False
    assert decision.reject_reason == "below_exit_channel"
