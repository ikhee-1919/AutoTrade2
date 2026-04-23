from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from app.data.providers.csv_provider import CSVDataProvider
from app.models.candle import Candle
from app.schemas.backtest import BacktestRunRequest
from app.schemas.walkforward import WalkforwardRunRequest
from app.strategy.base import StrategyContext
from app.strategy.samples.mtf_trend_pullback_strategy import MTFTrendPullbackStrategy


def _sample_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "sample"


def _candles(count: int, step: float = 0.4) -> list[Candle]:
    now = datetime(2025, 1, 1)
    rows = []
    price = 100.0
    for i in range(count):
        price += step
        rows.append(
            Candle(
                timestamp=now + timedelta(minutes=i * 5),
                open=price * 0.99,
                high=price * 1.01,
                low=price * 0.98,
                close=price,
                volume=1000 + i * 3,
            )
        )
    return rows


def test_timeframe_mapping_validation_required_roles(service_bundle) -> None:
    backtest_service = service_bundle["backtest_service"]
    with pytest.raises(ValueError, match="Missing required timeframe roles"):
        backtest_service.run(
            BacktestRunRequest(
                strategy_id="mtf_trend_pullback_v1",
                symbol="BTC-KRW",
                timeframe="1d",
                timeframe_mapping={"entry": "1d"},
                start_date=date(2025, 1, 1),
                end_date=date(2025, 3, 1),
            )
        )


def test_timeframe_mapping_validation_invalid_timeframe(service_bundle) -> None:
    backtest_service = service_bundle["backtest_service"]
    with pytest.raises(ValueError, match="unsupported timeframe"):
        backtest_service.run(
            BacktestRunRequest(
                strategy_id="mtf_trend_pullback_v1",
                symbol="BTC-KRW",
                timeframe="1d",
                timeframe_mapping={"trend": "2h", "setup": "1d", "entry": "1d"},
                start_date=date(2025, 1, 1),
                end_date=date(2025, 3, 1),
            )
        )


def test_provider_bundle_returns_role_metadata() -> None:
    provider = CSVDataProvider(_sample_dir())
    bundle = provider.load_timeframe_bundle(
        symbol="BTC-KRW",
        timeframe_mapping={"trend": "1d", "setup": "1d", "entry": "1d"},
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 20),
    )
    assert bundle["mapping"]["trend"] == "1d"
    assert set(bundle["candles_by_role"].keys()) == {"trend", "setup", "entry"}
    assert bundle["metadata_by_role"]["entry"]["source_type"] in {"sample", "collected"}


def test_mtf_strategy_evaluate_context_uses_roles() -> None:
    strategy = MTFTrendPullbackStrategy()
    params = strategy.default_params()
    context = StrategyContext(
        symbol="BTC-KRW",
        timeframe_mapping={"trend": "60m", "setup": "15m", "entry": "5m"},
        candles_by_role={
            "trend": _candles(80, step=0.3),
            "setup": _candles(30, step=0.05),
            "entry": _candles(20, step=0.2),
        },
        metadata_by_role={},
        as_of=datetime(2025, 1, 1, 12, 0),
        entry_role="entry",
    )
    decision = strategy.evaluate_context(context, params)
    assert decision.regime in {"bullish", "neutral", "bearish", "unknown"}
    assert isinstance(decision.entry_allowed, bool)
    assert isinstance(decision.score, float)
    assert "regime_by_role" in decision.debug_info


def test_backtest_run_with_timeframe_mapping_metadata(service_bundle) -> None:
    backtest_service = service_bundle["backtest_service"]
    result = backtest_service.run(
        BacktestRunRequest(
            strategy_id="mtf_trend_pullback_v1",
            symbol="BTC-KRW",
            timeframe="1d",
            timeframe_mapping={"trend": "1d", "setup": "1d", "entry": "1d"},
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
        )
    )
    assert result["timeframe_mapping"]["entry"] == "1d"
    assert "selected_datasets_by_role" in result
    assert "entry" in result["selected_datasets_by_role"]
    rerun = backtest_service.rerun(result["run_id"])
    assert rerun["timeframe_mapping"] == result["timeframe_mapping"]


def test_walkforward_run_with_timeframe_mapping(service_bundle) -> None:
    walkforward_service = service_bundle["walkforward_service"]
    result = walkforward_service.run(
        WalkforwardRunRequest(
            strategy_id="mtf_trend_pullback_v1",
            symbol="BTC-KRW",
            timeframe="1d",
            timeframe_mapping={"trend": "1d", "setup": "1d", "entry": "1d"},
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            train_window_size=60,
            test_window_size=30,
            step_size=30,
            window_unit="candles",
        )
    )
    assert result["timeframe_mapping"]["trend"] == "1d"
    assert len(result["segments"]) >= 2
    assert result["segments"][0]["timeframe_mapping"]["entry"] == "1d"


def test_backtest_and_walkforward_api_with_timeframe_mapping(api_client) -> None:
    backtest = api_client.post(
        "/backtests/run",
        json={
            "strategy_id": "mtf_trend_pullback_v1",
            "symbol": "BTC-KRW",
            "timeframe": "1d",
            "timeframe_mapping": {"trend": "1d", "setup": "1d", "entry": "1d"},
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
        },
    )
    assert backtest.status_code == 200
    back_body = backtest.json()
    assert back_body["timeframe_mapping"]["trend"] == "1d"
    assert "selected_datasets_by_role" in back_body

    walk = api_client.post(
        "/walkforward/run",
        json={
            "strategy_id": "mtf_trend_pullback_v1",
            "symbol": "BTC-KRW",
            "timeframe": "1d",
            "timeframe_mapping": {"trend": "1d", "setup": "1d", "entry": "1d"},
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
            "train_window_size": 60,
            "test_window_size": 30,
            "step_size": 30,
            "window_unit": "candles",
        },
    )
    assert walk.status_code == 200
    walk_body = walk.json()
    assert walk_body["timeframe_mapping"]["entry"] == "1d"


def test_new_strategy_backtest_api_integration(api_client) -> None:
    res = api_client.post(
        "/backtests/run",
        json={
            "strategy_id": "trend_momentum_volume_score_v2",
            "symbol": "BTC-KRW",
            "timeframe": "1d",
            "timeframe_mapping": {"trend": "1d", "entry": "1d"},
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["strategy_id"] == "trend_momentum_volume_score_v2"
    assert body["timeframe_mapping"]["entry"] == "1d"
