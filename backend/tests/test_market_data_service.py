from datetime import date
import json

from app.data.providers.csv_provider import CSVDataProvider
from app.schemas.market_data import MarketDataBatchRequest, MarketDataCollectRequest, MarketDataUpdateRequest


def test_collect_and_manifest_metadata(service_bundle) -> None:
    service = service_bundle["market_data_service"]
    result = service.collect(
        MarketDataCollectRequest(
            source="upbit",
            symbol="KRW-BTC",
            timeframe="1d",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 10),
        )
    )
    assert result["dataset_id"]
    assert result["saved_count"] > 0
    detail = service.get_dataset(result["dataset_id"])
    manifest = detail["manifest"]
    assert manifest["data_signature"]
    assert manifest["row_count"] == result["saved_count"]
    assert manifest["quality_status"] in {"pass", "warning", "fail"}


def test_incremental_update_and_dedup(service_bundle) -> None:
    service = service_bundle["market_data_service"]
    service.collect(
        MarketDataCollectRequest(
            source="upbit",
            symbol="KRW-ETH",
            timeframe="1d",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 5),
        )
    )
    updated = service.update(
        MarketDataUpdateRequest(
            source="upbit",
            symbol="KRW-ETH",
            timeframe="1d",
            end_date=date(2025, 1, 8),
        )
    )
    assert updated["saved_count"] >= 8
    assert updated["duplicate_removed_count"] >= 0


def test_quality_validation_detects_issues(service_bundle) -> None:
    service = service_bundle["market_data_service"]
    rows = [
        {"timestamp": "2025-01-01T00:00:00", "open": 10, "high": 12, "low": 9, "close": 11, "volume": 1},
        {"timestamp": "2025-01-01T00:00:00", "open": 10, "high": 12, "low": 9, "close": 11, "volume": 1},
        {"timestamp": "2025-01-03T00:00:00", "open": -1, "high": 8, "low": 9, "close": 10, "volume": 1},
    ]
    report = service.validate_rows(rows, timeframe="1d")
    assert report["duplicate_count"] > 0
    assert report["missing_interval_count"] > 0
    assert report["invalid_ohlc_count"] > 0
    assert report["status"] in {"warning", "fail"}


def test_collected_dataset_can_be_loaded_by_provider(service_bundle, tmp_path) -> None:
    service = service_bundle["market_data_service"]
    result = service.collect(
        MarketDataCollectRequest(
            source="upbit",
            symbol="KRW-XRP",
            timeframe="1d",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 7),
        )
    )
    market_root = service_bundle["market_repo"]._market_root  # test-only access
    provider = CSVDataProvider(sample_data_dir=tmp_path / "empty-sample", collected_data_dir=market_root)
    candles = provider.load_ohlcv(
        symbol="KRW-XRP",
        timeframe="1d",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 7),
    )
    assert len(candles) == result["saved_count"]


def test_batch_collect_combinations_and_summary(service_bundle) -> None:
    service = service_bundle["market_data_service"]
    batch = service.collect_batch(
        MarketDataBatchRequest(
            source="upbit",
            symbols=["KRW-BTC", "KRW-ETH"],
            timeframes=["5m", "1d"],
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 2),
            mode="full_collect",
            validate_after_collect=True,
            use_job=False,
        )
    )
    assert batch["total_requested_combinations"] == 4
    assert len(batch["items"]) == 4
    assert batch["completed_combinations"] + batch["failed_combinations"] + batch["skipped_combinations"] == 4
    summary = service.summary()
    assert "KRW-BTC" in summary["available_symbols"]
    assert "5m" in summary["available_timeframes"]


def test_batch_update_runs_incremental(service_bundle) -> None:
    service = service_bundle["market_data_service"]
    service.collect(
        MarketDataCollectRequest(
            source="upbit",
            symbol="KRW-BTC",
            timeframe="1d",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 3),
        )
    )
    batch = service.collect_batch(
        MarketDataBatchRequest(
            source="upbit",
            symbols=["KRW-BTC"],
            timeframes=["1d"],
            end_date=date(2025, 1, 5),
            mode="incremental_update",
            use_job=False,
        )
    )
    assert batch["total_requested_combinations"] == 1
    assert batch["completed_combinations"] == 1


def test_provider_fallback_when_collected_quality_fail(service_bundle, tmp_path) -> None:
    service = service_bundle["market_data_service"]
    service.collect(
        MarketDataCollectRequest(
            source="upbit",
            symbol="BTC-KRW",
            timeframe="1d",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 3),
        )
    )
    repo = service_bundle["market_repo"]
    manifest = repo.load_manifest("upbit", "BTC-KRW", "1d")
    assert manifest is not None
    manifest["quality_status"] = "fail"
    repo.save_manifest("upbit", "BTC-KRW", "1d", manifest)

    sample_dir = tmp_path / "sample"
    sample_dir.mkdir(parents=True, exist_ok=True)
    sample_file = sample_dir / "BTC-KRW_1d.csv"
    sample_file.write_text(
        "timestamp,open,high,low,close,volume\n"
        "2025-01-01T00:00:00,1,2,0.5,1.5,10\n",
        encoding="utf-8",
    )
    provider = CSVDataProvider(sample_data_dir=sample_dir, collected_data_dir=repo._market_root)  # noqa: SLF001
    candles = provider.load_ohlcv(
        symbol="KRW-BTC",
        timeframe="1d",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 2),
    )
    assert len(candles) == 1
    meta = provider.get_last_dataset_meta()
    assert meta is not None
    assert meta["source_type"] == "sample"
