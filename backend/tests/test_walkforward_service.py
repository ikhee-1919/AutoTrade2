from datetime import date
from pathlib import Path

from app.data.providers.csv_provider import CSVDataProvider
from app.schemas.walkforward import WalkforwardRunRequest


def _sample_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "sample"


def test_segment_generation_by_candles(service_bundle) -> None:
    service = service_bundle["walkforward_service"]
    candles = CSVDataProvider(_sample_dir()).load_ohlcv(
        "BTC-KRW",
        "1d",
        date(2025, 1, 1),
        date(2025, 12, 31),
    )
    segments = service.build_segments(
        candles=candles,
        train_window_size=60,
        test_window_size=30,
        step_size=30,
        window_unit="candles",
    )
    assert len(segments) >= 2
    assert segments[0]["train_start"] <= segments[0]["train_end"]
    assert segments[0]["test_start"] <= segments[0]["test_end"]
    anchored = service.build_segments(
        candles=candles,
        train_window_size=60,
        test_window_size=30,
        step_size=30,
        window_unit="candles",
        walkforward_mode="anchored",
    )
    assert len(anchored) >= 2
    assert anchored[0]["train_start"] == anchored[1]["train_start"]
    assert anchored[1]["train_end"] >= anchored[0]["train_end"]
    assert segments[0]["train_start"] != segments[1]["train_start"]


def test_walkforward_run_and_metadata(service_bundle) -> None:
    service = service_bundle["walkforward_service"]
    result = service.run(
        WalkforwardRunRequest(
            strategy_id="ma_regime_v1",
            symbol="ETH-KRW",
            timeframe="1d",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            train_window_size=60,
            test_window_size=30,
            step_size=30,
            window_unit="candles",
            walkforward_mode="rolling",
            benchmark_enabled=True,
        )
    )
    assert result["walkforward_run_id"]
    assert len(result["segments"]) >= 2
    assert result["strategy_version"]
    assert result["code_version"]
    assert result["walkforward_mode"] == "rolling"
    assert "execution_config" in result
    assert "params_snapshot" in result
    first_segment = result["segments"][0]
    assert "benchmark_buy_and_hold_return_pct" in first_segment
    assert "excess_return_pct" in first_segment


def test_walkforward_rerun_reproducibility(service_bundle) -> None:
    service = service_bundle["walkforward_service"]
    first = service.run(
        WalkforwardRunRequest(
            strategy_id="ma_regime_v1",
            symbol="SOL-KRW",
            timeframe="1d",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            train_window_size=60,
            test_window_size=30,
            step_size=30,
            window_unit="candles",
            walkforward_mode="anchored",
            fee_rate=0.0007,
            slippage_rate=0.0004,
            execution_policy="signal_close",
            benchmark_enabled=False,
        )
    )
    rerun = service.rerun(first["walkforward_run_id"])
    assert rerun["rerun_of_walkforward_run_id"] == first["walkforward_run_id"]
    assert rerun["walkforward_mode"] == "anchored"
    assert rerun["execution_config"]["fee_rate"] == first["execution_config"]["fee_rate"]
    assert rerun["execution_config"]["slippage_rate"] == first["execution_config"]["slippage_rate"]
    assert (
        rerun["execution_config"]["execution_policy"]
        == first["execution_config"]["execution_policy"]
    )
