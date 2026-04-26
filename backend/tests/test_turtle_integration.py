def test_turtle_backtest_run_api(api_client) -> None:
    response = api_client.post(
        "/backtests/run",
        json={
            "strategy_id": "turtle_breakout_v1",
            "symbol": "BTC-KRW",
            "timeframe": "1d",
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
            "params": {
                "breakout_entry_length": 20,
                "breakout_exit_length": 10,
                "atr_stop_multiple": 2.0,
            },
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["strategy_id"] == "turtle_breakout_v1"
    assert "summary" in payload


def test_turtle_walkforward_run_api(api_client) -> None:
    response = api_client.post(
        "/walkforward/run",
        json={
            "strategy_id": "turtle_breakout_v1",
            "symbol": "ETH-KRW",
            "timeframe": "1d",
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
            "train_window_size": 240,
            "test_window_size": 30,
            "step_size": 30,
            "window_unit": "candles",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["strategy_id"] == "turtle_breakout_v1"
    assert payload["segments"]


def test_turtle_sweep_compatibility(api_client) -> None:
    response = api_client.post(
        "/sweeps/run",
        json={
            "strategy_id": "turtle_breakout_v1",
            "symbol": "SOL-KRW",
            "timeframe": "1d",
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
            "use_job": False,
            "sweep_space": {
                "breakout_entry_length": [20, 30],
                "breakout_exit_length": [10, 15],
                "atr_stop_multiple": [1.5, 2.0],
                "trend_ma_length": [100, 200],
            },
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["strategy_id"] == "turtle_breakout_v1"
    assert payload["total_combinations"] == 16
    assert payload["completed_combinations"] + payload["failed_combinations"] == 16
