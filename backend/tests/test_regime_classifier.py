from datetime import datetime, timedelta

from app.models.candle import Candle
from app.services.regime_classifier import RegimeClassifier


def _daily_candles(closes: list[float], start: datetime = datetime(2024, 1, 1)) -> list[Candle]:
    rows: list[Candle] = []
    for idx, close in enumerate(closes):
        rows.append(
            Candle(
                timestamp=start + timedelta(days=idx),
                open=close * 0.995,
                high=close * 1.01,
                low=close * 0.99,
                close=close,
                volume=1000 + idx,
            )
        )
    return rows


def test_regime_classifier_bull_above_200() -> None:
    closes = [100 + i * 0.6 for i in range(320)]
    classifier = RegimeClassifier()
    point = classifier.classify_last(_daily_candles(closes))
    assert point is not None
    assert point.has_sufficient_history is True
    assert point.regime == "bull_above_200"


def test_regime_classifier_above_200_weak() -> None:
    closes = [120 - 0.1 * i for i in range(260)] + [105.0 for _ in range(40)]
    classifier = RegimeClassifier()
    point = classifier.classify_last(_daily_candles(closes))
    assert point is not None
    assert point.has_sufficient_history is True
    assert point.regime == "above_200_weak"


def test_regime_classifier_below_200_recovery() -> None:
    closes = [100.0 for _ in range(260)] + [98.0 for _ in range(40)] + [99.0 for _ in range(20)]
    classifier = RegimeClassifier()
    point = classifier.classify_last(_daily_candles(closes))
    assert point is not None
    assert point.has_sufficient_history is True
    assert point.regime == "below_200_recovery"


def test_regime_classifier_below_200_downtrend() -> None:
    closes = [220 - i * 0.45 for i in range(320)]
    classifier = RegimeClassifier()
    point = classifier.classify_last(_daily_candles(closes))
    assert point is not None
    assert point.has_sufficient_history is True
    assert point.regime == "below_200_downtrend"


def test_regime_classifier_insufficient_history() -> None:
    closes = [100 + i * 0.2 for i in range(120)]
    classifier = RegimeClassifier()
    point = classifier.classify_last(_daily_candles(closes))
    assert point is not None
    assert point.has_sufficient_history is False
    assert point.regime == "insufficient_history"
