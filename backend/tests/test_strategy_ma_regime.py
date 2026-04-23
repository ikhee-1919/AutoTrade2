from datetime import datetime, timedelta

from app.models.candle import Candle
from app.strategy.samples.ma_regime_strategy import MovingAverageRegimeStrategy


def _candles(count: int, start: float = 100.0, step: float = 0.4) -> list[Candle]:
    now = datetime(2025, 1, 1)
    rows = []
    price = start
    for i in range(count):
        price += step
        rows.append(
            Candle(
                timestamp=now + timedelta(days=i),
                open=price * 0.99,
                high=price * 1.01,
                low=price * 0.98,
                close=price,
                volume=2000 + i * 5,
            )
        )
    return rows


def test_regime_and_entry_decision_fields_exist() -> None:
    strategy = MovingAverageRegimeStrategy()
    candles = _candles(80)
    decision = strategy.evaluate(candles, strategy.default_params())

    assert decision.regime in {"bullish", "neutral", "bearish", "unknown"}
    assert isinstance(decision.entry_allowed, bool)
    assert isinstance(decision.score, float)
    assert decision.stop_loss is not None
    assert decision.take_profit is not None


def test_reject_reason_present_when_entry_blocked() -> None:
    strategy = MovingAverageRegimeStrategy()
    candles = _candles(80, step=-0.2)
    decision = strategy.evaluate(candles, strategy.default_params())

    if not decision.entry_allowed:
        assert decision.reject_reason is not None
