from datetime import date


def test_top10_refresh_selects_dynamic_markets(service_bundle) -> None:
    svc = service_bundle["top10_service"]
    universe = svc.refresh_universe(market_scope="KRW", top_n=10)
    assert universe["selected_count"] == 10
    assert len(universe["selected_markets"]) == 10
    assert all(m.startswith("KRW-") for m in universe["selected_markets"])


def test_top10_collect_all_combinations(service_bundle) -> None:
    svc = service_bundle["top10_service"]
    svc.refresh_universe(market_scope="KRW", top_n=10)
    result = svc.collect_all(
        include_seconds=False,
        validate_after_collect=True,
        overwrite_existing=False,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 3),
    )
    assert result["total_requested_combinations"] == 10 * 12
    assert result["completed_combinations"] + result["failed_combinations"] + result["skipped_combinations"] == 120


def test_top10_summary_has_quality_counts(service_bundle) -> None:
    svc = service_bundle["top10_service"]
    svc.refresh_universe(market_scope="KRW", top_n=5)
    svc.collect_all(
        include_seconds=False,
        validate_after_collect=True,
        overwrite_existing=False,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 2),
    )
    summary = svc.summary(include_seconds=False)
    assert summary["total_combinations"] == 5 * 12
    assert summary["pass_count"] + summary["warning_count"] + summary["fail_count"] + summary["missing_dataset_count"] == summary["total_combinations"]
    assert len(summary["coverage_by_symbol"]) == 5
