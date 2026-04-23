import time


def _wait_sweep_job(client, job_id: str, timeout: float = 20.0) -> dict:
    started = time.time()
    while time.time() - started < timeout:
        job = client.get(f"/sweeps/jobs/{job_id}").json()
        if job["status"] in {"completed", "failed", "cancelled"}:
            return job
        time.sleep(0.1)
    raise AssertionError("sweep job timeout")


def test_sweep_run_list_detail_and_top(api_client) -> None:
    payload = {
        "strategy_id": "ma_regime_v1",
        "symbol": "BTC-KRW",
        "timeframe": "1d",
        "start_date": "2025-01-01",
        "end_date": "2025-12-31",
        "sweep_space": {"score_threshold": [0.6, 0.7], "volume_multiplier": [1.0, 1.2]},
        "use_job": False,
    }
    run = api_client.post("/sweeps/run", json=payload)
    assert run.status_code == 200
    body = run.json()
    assert body["sweep_run_id"]
    assert body["total_combinations"] == 4

    listing = api_client.get("/sweeps")
    assert listing.status_code == 200
    assert any(item["sweep_run_id"] == body["sweep_run_id"] for item in listing.json()["items"])

    detail = api_client.get(f"/sweeps/{body['sweep_run_id']}")
    assert detail.status_code == 200
    assert detail.json()["sweep_run_id"] == body["sweep_run_id"]

    results = api_client.get(f"/sweeps/{body['sweep_run_id']}/results")
    assert results.status_code == 200
    assert results.json()["total"] == 4

    top = api_client.get(f"/sweeps/{body['sweep_run_id']}/top?limit=2")
    assert top.status_code == 200
    assert len(top.json()["items"]) <= 2


def test_sweep_job_progress_and_rerun(api_client) -> None:
    payload = {
        "strategy_id": "mtf_trend_pullback_v1",
        "symbol": "BTC-KRW",
        "timeframe": "1d",
        "timeframe_mapping": {"trend": "1d", "setup": "1d", "entry": "1d"},
        "start_date": "2025-01-01",
        "end_date": "2025-12-31",
        "sweep_space": {"score_threshold": [0.6, 0.7, 0.8]},
        "use_job": True,
    }
    job = api_client.post("/sweeps/run", json=payload)
    assert job.status_code == 200
    job_body = job.json()
    assert job_body["job_type"] == "parameter_sweep"
    terminal = _wait_sweep_job(api_client, job_body["job_id"])
    assert terminal["status"] in {"completed", "failed", "cancelled"}
    assert "completed_combinations" in terminal
    assert "failed_combinations" in terminal

    if terminal["status"] == "completed":
        rerun = api_client.post(f"/sweeps/rerun/{terminal['related_sweep_run_id']}")
        assert rerun.status_code == 200
        assert rerun.json()["rerun_of_sweep_run_id"] == terminal["related_sweep_run_id"]
