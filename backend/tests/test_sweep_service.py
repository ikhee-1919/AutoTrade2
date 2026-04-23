from datetime import date

from app.schemas.sweep import SweepRunRequest


def test_grid_combinations_generation(service_bundle) -> None:
    service = service_bundle["sweep_service"]
    combos = service._build_combinations(  # noqa: SLF001 - direct unit test
        {
            "short_window": [10, 20],
            "score_threshold": [0.6, 0.7, 0.8],
        }
    )
    assert len(combos) == 6
    assert all("short_window" in item and "score_threshold" in item for item in combos)


def test_sweep_run_save_and_ranking(service_bundle) -> None:
    service = service_bundle["sweep_service"]
    result = service.run(
        SweepRunRequest(
            strategy_id="ma_regime_v1",
            symbol="BTC-KRW",
            timeframe="1d",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            sweep_space={"score_threshold": [0.6, 0.7], "volume_multiplier": [1.0, 1.2]},
            use_job=False,
        )
    )
    assert result["sweep_run_id"]
    assert result["total_combinations"] == 4
    assert len(result["results"]) == 4
    assert "best_by_net_return" in result["ranking_summary"]
    listed = service.list_runs(limit=5)
    assert listed and listed[0]["sweep_run_id"] == result["sweep_run_id"]


def test_sweep_mtf_with_timeframe_mapping(service_bundle) -> None:
    service = service_bundle["sweep_service"]
    result = service.run(
        SweepRunRequest(
            strategy_id="mtf_trend_pullback_v1",
            symbol="BTC-KRW",
            timeframe="1d",
            timeframe_mapping={"trend": "1d", "setup": "1d", "entry": "1d"},
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            sweep_space={"score_threshold": [0.6, 0.7]},
            use_job=False,
        )
    )
    assert result["timeframe_mapping"]["entry"] == "1d"
    assert result["completed_combinations"] + result["failed_combinations"] == 2


def test_sweep_rerun_reproducibility(service_bundle) -> None:
    service = service_bundle["sweep_service"]
    first = service.run(
        SweepRunRequest(
            strategy_id="ma_regime_v1",
            symbol="ETH-KRW",
            timeframe="1d",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            sweep_space={"score_threshold": [0.6, 0.8]},
            use_job=False,
        )
    )
    rerun = service.rerun(first["sweep_run_id"])
    assert rerun["rerun_of_sweep_run_id"] == first["sweep_run_id"]
    assert rerun["sweep_space"] == first["sweep_space"]
    assert rerun["timeframe_mapping"] == first["timeframe_mapping"]
