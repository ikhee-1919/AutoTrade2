import time


def _wait_for_walkforward_terminal(client, job_id: str, timeout: float = 15.0) -> dict:
    started = time.time()
    saw_progress = False
    while time.time() - started < timeout:
        job = client.get(f"/walkforward/jobs/{job_id}").json()
        if (job.get("progress") or 0) > 0:
            saw_progress = True
        if job["status"] in {"completed", "failed", "cancelled"}:
            job["_saw_progress"] = saw_progress
            return job
        time.sleep(0.15)
    raise AssertionError("walkforward job timeout")


def test_walkforward_run_detail_list_and_rerun(api_client) -> None:
    payload = {
        "strategy_id": "ma_regime_v1",
        "symbol": "BTC-KRW",
        "timeframe": "1d",
        "timeframe_mapping": {"entry": "1d"},
        "start_date": "2025-01-01",
        "end_date": "2025-12-31",
        "train_window_size": 60,
        "test_window_size": 30,
        "step_size": 30,
        "window_unit": "candles",
        "walkforward_mode": "rolling",
        "benchmark_enabled": True,
    }
    run = api_client.post("/walkforward/run", json=payload)
    assert run.status_code == 200
    body = run.json()
    assert body["walkforward_run_id"]
    assert len(body["segments"]) >= 2
    assert body["walkforward_mode"] == "rolling"
    assert body["timeframe_mapping"]["entry"] == "1d"
    assert "summary" in body
    assert "diagnostics" in body

    detail = api_client.get(f"/walkforward/{body['walkforward_run_id']}")
    assert detail.status_code == 200
    assert detail.json()["walkforward_run_id"] == body["walkforward_run_id"]
    assert detail.json().get("timeframe_mapping", {}).get("entry") == "1d"

    listing = api_client.get("/walkforward?limit=10")
    assert listing.status_code == 200
    assert listing.json()["items"]

    rerun = api_client.post(f"/walkforward/rerun/{body['walkforward_run_id']}")
    assert rerun.status_code == 200
    assert rerun.json()["rerun_of_walkforward_run_id"] == body["walkforward_run_id"]


def test_walkforward_compare_and_jobs_progress(api_client) -> None:
    payload = {
        "strategy_id": "ma_regime_v1",
        "symbol": "ETH-KRW",
        "timeframe": "1d",
        "timeframe_mapping": {"entry": "1d"},
        "start_date": "2025-01-01",
        "end_date": "2025-12-31",
        "train_window_size": 60,
        "test_window_size": 30,
        "step_size": 30,
        "window_unit": "candles",
        "walkforward_mode": "anchored",
    }
    run1 = api_client.post("/walkforward/run", json=payload).json()
    run2 = api_client.post("/walkforward/run", json={**payload, "symbol": "SOL-KRW"}).json()
    comp = api_client.get(
        f"/walkforward/compare?walkforward_run_ids={run1['walkforward_run_id']}&walkforward_run_ids={run2['walkforward_run_id']}"
    )
    assert comp.status_code == 200
    comp_body = comp.json()
    assert comp_body["compared_count"] == 2
    assert "best_walkforward_run_id" in comp_body
    assert all("walkforward_mode" in item for item in comp_body["items"])
    csv_res = api_client.get(
        f"/walkforward/compare.csv?walkforward_run_ids={run1['walkforward_run_id']}&walkforward_run_ids={run2['walkforward_run_id']}"
    )
    assert csv_res.status_code == 200
    assert "text/csv" in csv_res.headers.get("content-type", "")
    assert "walkforward_run_id" in csv_res.text
    assert run1["walkforward_run_id"] in csv_res.text

    job = api_client.post("/walkforward/jobs", json=payload)
    assert job.status_code == 200
    terminal = _wait_for_walkforward_terminal(api_client, job.json()["job_id"])
    assert terminal["status"] in {"completed", "failed", "cancelled"}
    assert terminal["_saw_progress"] is True
    assert "segment_total" in terminal
    assert "segment_completed" in terminal


def test_walkforward_batch_run_api(api_client) -> None:
    payload = {
        "strategy_id": "ma_regime_v1",
        "symbols": ["BTC-KRW", "ETH-KRW"],
        "timeframe": "1d",
        "start_date": "2025-01-01",
        "end_date": "2025-12-31",
        "train_window_size": 60,
        "test_window_size": 30,
        "step_size": 30,
        "window_unit": "candles",
        "walkforward_modes": ["rolling", "anchored"],
        "use_jobs": True,
    }
    res = api_client.post("/walkforward/batch-run", json=payload)
    assert res.status_code == 200
    body = res.json()
    assert body["batch_id"]
    assert body["total_requested"] == 4
    assert len(body["items"]) == 4
    assert all(item.get("job_id") for item in body["items"])
