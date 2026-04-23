from datetime import datetime, timedelta

from app.models.candle import Candle
from app.strategy.base import StrategyContext
from app.strategy.samples.trend_momentum_volume_score_v2 import TrendMomentumVolumeScoreV2Strategy


def _make_candles(
    count: int,
    start: datetime,
    step: timedelta,
    drift: float = 0.2,
    noise: float = 0.1,
    volume_base: float = 1000.0,
) -> list[Candle]:
    rows: list[Candle] = []
    price = 100.0
    for i in range(count):
        price += drift
        low = price - (0.4 + noise)
        high = price + (0.6 + noise)
        open_p = price - 0.2
        close_p = price + 0.25
        rows.append(
            Candle(
                timestamp=start + i * step,
                open=open_p,
                high=high,
                low=low,
                close=close_p,
                volume=volume_base + i * 4,
            )
        )
    return rows


def test_param_validation_errors() -> None:
    strategy = TrendMomentumVolumeScoreV2Strategy()
    try:
        strategy.validate_params({"min_atr_pct": 0.03, "max_atr_pct": 0.01})
        assert False, "expected validation error"
    except ValueError as exc:
        assert "min_atr_pct" in str(exc)


def test_entry_allowed_case() -> None:
    strategy = TrendMomentumVolumeScoreV2Strategy()
    trend = _make_candles(80, datetime(2025, 1, 1), timedelta(hours=1), drift=0.4, volume_base=1800)
    entry = _make_candles(120, datetime(2025, 1, 1), timedelta(minutes=5), drift=0.15, volume_base=900)
    # Force recent pullback touch + reclaim and volume surge.
    for i in range(-5, 0):
        entry[i] = Candle(
            timestamp=entry[i].timestamp,
            open=entry[i].open,
            high=entry[i].high,
            low=entry[i].low - 0.6,
            close=entry[i].close,
            volume=entry[i].volume * (1.1 if i < -1 else 2.8),
        )

    ctx = StrategyContext(
        symbol="BTC-KRW",
        timeframe_mapping={"trend": "60m", "entry": "5m"},
        candles_by_role={"trend": trend, "entry": entry},
        metadata_by_role={"entry": {}},
        as_of=entry[-1].timestamp,
        entry_role="entry",
    )
    decision = strategy.evaluate_context(ctx, strategy.default_params())
    assert isinstance(decision.score, float)
    assert decision.strategy_version == strategy.metadata().version
    assert "signals" in decision.debug_info


def test_reject_reason_case() -> None:
    strategy = TrendMomentumVolumeScoreV2Strategy()
    trend = _make_candles(80, datetime(2025, 1, 1), timedelta(hours=1), drift=-0.1, volume_base=1000)
    entry = _make_candles(120, datetime(2025, 1, 1), timedelta(minutes=5), drift=0.02, volume_base=500)
    ctx = StrategyContext(
        symbol="BTC-KRW",
        timeframe_mapping={"trend": "60m", "entry": "5m"},
        candles_by_role={"trend": trend, "entry": entry},
        metadata_by_role={"entry": {}},
        as_of=entry[-1].timestamp,
        entry_role="entry",
    )
    decision = strategy.evaluate_context(ctx, strategy.default_params())
    assert decision.entry_allowed is False
    assert decision.reject_reason is not None
