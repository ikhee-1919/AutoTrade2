from app.repositories.backtest_job_repository import BacktestJobRepository
from app.repositories.backtest_run_repository import BacktestRunRepository
from app.repositories.market_data_repository import MarketDataRepository
from app.repositories.walkforward_run_repository import WalkforwardRunRepository


def test_run_repository_stores_extended_metadata(tmp_path) -> None:
    repo = BacktestRunRepository(tmp_path / "runs.json")
    repo.save_run(
        {
            "run_id": "run-1",
            "run_at": "2025-01-01T00:00:00",
            "strategy_id": "ma_regime_v1",
            "strategy_version": "1.0.0",
            "code_version": "abc123",
            "symbol": "BTC-KRW",
            "timeframe": "1d",
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
            "params_used": {"x": 1},
            "params_snapshot": {"x": 1},
            "params_hash": "hash",
            "data_signature": {
                "source": "csv",
                "candle_count": 1,
                "first_timestamp": "2025-01-01T00:00:00",
                "last_timestamp": "2025-01-01T00:00:00",
                "candles_hash": "h",
            },
            "summary": {"total_return_pct": 0, "trade_count": 0, "win_rate": 0, "max_drawdown": 0, "avg_profit": 0, "avg_loss": 0},
            "trades": [],
            "diagnostics": {"reject_reason_counts": {}, "regime_counts": {}},
            "equity_curve": [],
        }
    )

    item = repo.get_by_id("run-1")
    assert item is not None
    assert item["code_version"] == "abc123"
    assert "params_snapshot" in item


def test_job_repository_save_update_and_query(tmp_path) -> None:
    repo = BacktestJobRepository(tmp_path / "jobs.json")
    repo.create(
        {
            "job_id": "job-1",
            "job_type": "backtest",
            "status": "queued",
            "progress": 0,
            "request_hash": "abc",
            "request": {},
            "created_at": "2025-01-01T00:00:00",
        }
    )
    updated = repo.update("job-1", {"status": "running", "progress": 10})
    assert updated is not None
    assert updated["status"] == "running"
    assert repo.count_by_status(["running"]) == 1
    assert repo.get_latest_active_by_request_hash("abc") is not None


def test_walkforward_repository_save_and_get(tmp_path) -> None:
    repo = WalkforwardRunRepository(tmp_path / "walkforward_runs.json")
    repo.save_run(
        {
            "walkforward_run_id": "wf-1",
            "request_hash": "wfhash",
            "created_at": "2026-01-01T00:00:00",
            "strategy_id": "ma_regime_v1",
            "strategy_version": "1.0.0",
            "code_version": "abc123",
            "symbol": "BTC-KRW",
            "timeframe": "1d",
            "requested_period": {"start_date": "2025-01-01", "end_date": "2025-12-31"},
            "execution_config": {"execution_policy": "next_open"},
            "params_snapshot": {"strategy_params": {}, "execution_config": {}},
            "train_window_size": 60,
            "test_window_size": 30,
            "step_size": 30,
            "window_unit": "candles",
            "benchmark_enabled": True,
            "segments": [],
            "summary": {"segment_count": 0, "completed_segment_count": 0, "total_net_return_pct": 0.0, "average_segment_return_pct": 0.0, "median_segment_return_pct": 0.0, "worst_segment_return_pct": 0.0, "best_segment_return_pct": 0.0, "average_max_drawdown": 0.0, "total_trade_count": 0},
            "diagnostics": {"profitable_segments": 0, "losing_segments": 0, "segments_beating_benchmark": 0, "segments_underperforming_benchmark": 0},
            "interpretation_summary": "n/a",
        }
    )
    item = repo.get_by_id("wf-1")
    assert item is not None
    assert item["code_version"] == "abc123"
    assert item["request_hash"] == "wfhash"


def test_market_data_repository_manifest_and_rows(tmp_path) -> None:
    repo = MarketDataRepository(
        index_file=tmp_path / "market_data_datasets.json",
        market_root=tmp_path / "market",
    )
    repo.save_rows(
        "upbit",
        "KRW-BTC",
        "1d",
        [
            {
                "timestamp": "2025-01-01T00:00:00",
                "open": 1,
                "high": 2,
                "low": 0.5,
                "close": 1.5,
                "volume": 10,
            }
        ],
    )
    manifest = {
        "dataset_id": repo.dataset_id("upbit", "KRW-BTC", "1d"),
        "source": "upbit",
        "symbol": "KRW-BTC",
        "timeframe": "1d",
        "start_at": "2025-01-01T00:00:00",
        "end_at": "2025-01-01T00:00:00",
        "row_count": 1,
        "created_at": "2025-01-01T00:00:00",
        "updated_at": "2025-01-01T00:00:00",
        "data_signature": "sig",
        "quality_status": "pass",
        "quality_report_summary": "ok",
        "path": "dummy",
    }
    repo.save_manifest("upbit", "KRW-BTC", "1d", manifest)
    item = repo.get_by_dataset_id(manifest["dataset_id"])
    assert item is not None
    assert item["data_signature"] == "sig"
    rows = repo.load_rows("upbit", "KRW-BTC", "1d")
    assert len(rows) == 1
