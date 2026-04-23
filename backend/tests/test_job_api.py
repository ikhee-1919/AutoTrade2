import time


def _wait_for_terminal(client, job_id: str, timeout: float = 10.0) -> dict:
    started = time.time()
    while time.time() - started < timeout:
        job = client.get(f"/backtests/jobs/{job_id}").json()
        if job["status"] in {"completed", "failed", "cancelled"}:
            return job
        time.sleep(0.1)
    raise AssertionError("job timeout")


def test_job_create_status_and_progress(api_client) -> None:
    res = api_client.post(
        "/backtests/jobs",
        json={
            "strategy_id": "ma_regime_v1",
            "symbol": "BTC-KRW",
            "timeframe": "1d",
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
        },
    )
    assert res.status_code == 200
    job = res.json()
    assert "job_id" in job
    assert "progress" in job

    terminal = _wait_for_terminal(api_client, job["job_id"])
    assert terminal["status"] in {"completed", "failed", "cancelled"}


def test_job_cancel_and_retry(api_client) -> None:
    j1 = api_client.post(
        "/backtests/jobs",
        json={
            "strategy_id": "ma_regime_v1",
            "symbol": "BTC-KRW",
            "timeframe": "1d",
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
        },
    ).json()
    j2 = api_client.post(
        "/backtests/jobs",
        json={
            "strategy_id": "ma_regime_v1",
            "symbol": "ETH-KRW",
            "timeframe": "1d",
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
        },
    ).json()

    cancel = api_client.post(f"/backtests/jobs/{j2['job_id']}/cancel")
    assert cancel.status_code == 200
    assert cancel.json()["status"] == "cancelled"

    failed_job = api_client.post(
        "/backtests/jobs",
        json={
            "strategy_id": "ma_regime_v1",
            "symbol": "UNKNOWN-KRW",
            "timeframe": "1d",
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
        },
    ).json()
    failed_terminal = _wait_for_terminal(api_client, failed_job["job_id"])
    assert failed_terminal["status"] == "failed"

    retry = api_client.post(f"/backtests/jobs/{failed_job['job_id']}/retry")
    assert retry.status_code == 200
    assert retry.json()["retry_count"] >= 1


def test_job_filters(api_client) -> None:
    res = api_client.get("/backtests/jobs?status=running&job_type=backtest")
    assert res.status_code == 200
    assert "items" in res.json()
