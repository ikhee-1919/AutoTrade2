import time


def _wait_market_job(client, job_id: str, timeout: float = 12.0) -> dict:
    started = time.time()
    while time.time() - started < timeout:
        job = client.get(f"/market-data/jobs/{job_id}").json()
        if job["status"] in {"completed", "failed", "cancelled"}:
            return job
        time.sleep(0.1)
    raise AssertionError("market-data job timeout")


def test_market_data_collect_list_detail_preview_validate(api_client) -> None:
    collect = api_client.post(
        "/market-data/collect",
        json={
            "source": "upbit",
            "symbol": "KRW-BTC",
            "timeframe": "1d",
            "start_date": "2025-01-01",
            "end_date": "2025-01-10",
            "use_job": False,
        },
    )
    assert collect.status_code == 200
    body = collect.json()
    assert body["mode"] == "sync"
    dataset_id = body["result"]["dataset_id"]

    listing = api_client.get("/market-data")
    assert listing.status_code == 200
    assert any(item["dataset_id"] == dataset_id for item in listing.json()["items"])

    detail = api_client.get(f"/market-data/{dataset_id}")
    assert detail.status_code == 200
    assert detail.json()["manifest"]["dataset_id"] == dataset_id

    preview = api_client.get(f"/market-data/{dataset_id}/preview?limit=5&tail=true")
    assert preview.status_code == 200
    assert len(preview.json()["rows"]) <= 5

    validate = api_client.post(f"/market-data/{dataset_id}/validate", json={"use_job": False})
    assert validate.status_code == 200
    assert validate.json()["mode"] == "sync"


def test_market_data_update_and_job_flow(api_client) -> None:
    api_client.post(
        "/market-data/collect",
        json={
            "source": "upbit",
            "symbol": "KRW-ETH",
            "timeframe": "1d",
            "start_date": "2025-01-01",
            "end_date": "2025-01-05",
            "use_job": False,
        },
    )
    update_job = api_client.post(
        "/market-data/update",
        json={
            "source": "upbit",
            "symbol": "KRW-ETH",
            "timeframe": "1d",
            "end_date": "2025-01-12",
            "use_job": True,
        },
    )
    assert update_job.status_code == 200
    assert update_job.json()["mode"] == "job"
    terminal = _wait_market_job(api_client, update_job.json()["job_id"])
    assert terminal["status"] in {"completed", "failed", "cancelled"}

    jobs = api_client.get("/market-data/jobs?limit=20")
    assert jobs.status_code == 200
    assert "items" in jobs.json()


def test_market_data_collect_job_and_retry(api_client) -> None:
    job = api_client.post(
        "/market-data/collect",
        json={
            "source": "upbit",
            "symbol": "KRW-SOL",
            "timeframe": "1d",
            "start_date": "2025-01-01",
            "end_date": "2025-01-04",
            "use_job": True,
        },
    )
    assert job.status_code == 200
    job_id = job.json()["job_id"]
    terminal = _wait_market_job(api_client, job_id)
    assert terminal["status"] in {"completed", "failed", "cancelled"}

    bad = api_client.post(
        "/market-data/update",
        json={
            "source": "upbit",
            "symbol": "KRW-NOT-EXIST",
            "timeframe": "1d",
            "use_job": True,
        },
    )
    assert bad.status_code == 200
    bad_terminal = _wait_market_job(api_client, bad.json()["job_id"])
    assert bad_terminal["status"] == "failed"
    retry = api_client.post(f"/market-data/jobs/{bad_terminal['job_id']}/retry")
    assert retry.status_code == 200


def test_market_data_batch_collect_update_and_summary(api_client) -> None:
    collect_batch = api_client.post(
        "/market-data/collect-batch",
        json={
            "source": "upbit",
            "symbols": ["KRW-BTC", "KRW-ETH"],
            "timeframes": ["5m", "1d"],
            "start_date": "2025-01-01",
            "end_date": "2025-01-03",
            "mode": "full_collect",
            "validate_after_collect": True,
            "use_job": False,
        },
    )
    assert collect_batch.status_code == 200
    body = collect_batch.json()
    assert body["mode"] == "sync"
    assert body["total_requested_combinations"] == 4
    assert len(body["items"]) == 4

    summary = api_client.get("/market-data/summary")
    assert summary.status_code == 200
    payload = summary.json()
    assert "KRW-BTC" in payload["available_symbols"]
    assert "5m" in payload["available_timeframes"]
    assert "1d" in payload["available_timeframes"]

    by_symbol = api_client.get("/market-data/by-symbol/KRW-BTC")
    assert by_symbol.status_code == 200
    assert all(item["symbol"] == "KRW-BTC" for item in by_symbol.json()["items"])

    update_batch = api_client.post(
        "/market-data/update-batch",
        json={
            "source": "upbit",
            "symbols": ["KRW-BTC", "KRW-ETH"],
            "timeframes": ["5m", "1d"],
            "end_date": "2025-01-04",
            "mode": "incremental_update",
            "validate_after_collect": False,
            "use_job": False,
        },
    )
    assert update_batch.status_code == 200
    update_body = update_batch.json()
    assert update_body["mode"] == "sync"
    assert update_body["total_requested_combinations"] == 4
    assert update_body["completed_combinations"] + update_body["failed_combinations"] + update_body["skipped_combinations"] == 4


def test_market_data_batch_job_progress_fields(api_client) -> None:
    queued = api_client.post(
        "/market-data/collect-batch",
        json={
            "source": "upbit",
            "symbols": ["KRW-BTC", "KRW-ETH"],
            "timeframes": ["1d"],
            "start_date": "2025-01-01",
            "end_date": "2025-01-03",
            "mode": "full_collect",
            "validate_after_collect": False,
            "use_job": True,
        },
    )
    assert queued.status_code == 200
    body = queued.json()
    assert body["mode"] == "job"
    assert body["job_id"]

    terminal = _wait_market_job(api_client, body["job_id"])
    assert terminal["status"] in {"completed", "failed", "cancelled"}
    assert terminal["total_combinations"] is not None
    assert "completed_combinations" in terminal
    assert "failed_combinations" in terminal


def test_top10_universe_refresh_collect_summary(api_client) -> None:
    refresh = api_client.post(
        "/market-data/top10-universe/refresh",
        json={"market_scope": "KRW", "top_n": 10, "use_job": False},
    )
    assert refresh.status_code == 200
    assert refresh.json()["mode"] == "sync"

    current = api_client.get("/market-data/top10-universe")
    assert current.status_code == 200
    payload = current.json()
    assert payload["selected_count"] == 10
    assert len(payload["selected_markets"]) == 10

    collect = api_client.post(
        "/market-data/top10-universe/collect-all",
        json={
            "include_seconds": False,
            "validate_after_collect": True,
            "overwrite_existing": False,
            "use_job": False,
            "start_date": "2025-01-01",
            "end_date": "2025-01-03",
        },
    )
    assert collect.status_code == 200
    assert collect.json()["mode"] == "sync"

    summary = api_client.get("/market-data/top10-universe/summary")
    assert summary.status_code == 200
    s = summary.json()
    assert s["total_combinations"] == 120
    assert len(s["coverage_by_symbol"]) == 10


def test_top10_universe_jobs(api_client) -> None:
    refresh_job = api_client.post(
        "/market-data/top10-universe/refresh",
        json={"market_scope": "KRW", "top_n": 1, "use_job": True},
    )
    assert refresh_job.status_code == 200
    refresh_terminal = _wait_market_job(api_client, refresh_job.json()["job_id"])
    assert refresh_terminal["status"] in {"completed", "failed", "cancelled"}

    collect_job = api_client.post(
        "/market-data/top10-universe/collect-all",
        json={
            "include_seconds": False,
            "validate_after_collect": False,
            "overwrite_existing": False,
            "use_job": True,
            "start_date": "2025-01-01",
            "end_date": "2025-01-03",
        },
    )
    assert collect_job.status_code == 200
    collect_terminal = _wait_market_job(api_client, collect_job.json()["job_id"])
    assert collect_terminal["status"] in {"completed", "failed", "cancelled"}
    assert collect_terminal.get("total_combinations") is not None


def test_top10_universe_missing_and_retry_missing(api_client) -> None:
    refresh = api_client.post(
        "/market-data/top10-universe/refresh",
        json={"market_scope": "KRW", "top_n": 3, "use_job": False},
    )
    assert refresh.status_code == 200

    missing_before = api_client.get("/market-data/top10-universe/missing?include_seconds=false")
    assert missing_before.status_code == 200
    total_missing = missing_before.json()["total_missing"]
    assert total_missing > 0

    retry_sync = api_client.post(
        "/market-data/top10-universe/retry-missing",
        json={
            "include_seconds": False,
            "validate_after_collect": True,
            "overwrite_existing": False,
            "use_job": False,
            "start_date": "2025-01-01",
            "end_date": "2025-01-02",
        },
    )
    assert retry_sync.status_code == 200
    assert retry_sync.json()["mode"] == "sync"

    retry_job = api_client.post(
        "/market-data/top10-universe/retry-missing",
        json={
            "include_seconds": False,
            "validate_after_collect": False,
            "overwrite_existing": False,
            "use_job": True,
            "start_date": "2025-01-01",
            "end_date": "2025-01-02",
        },
    )
    assert retry_job.status_code == 200
    terminal = _wait_market_job(api_client, retry_job.json()["job_id"])
    assert terminal["status"] in {"completed", "failed", "cancelled"}
