def test_turtle_spot_long_v2_backtest_api(api_client) -> None:
    response = api_client.post(
        "/backtests/run",
        json={
            "strategy_id": "turtle_spot_long_v2",
            "symbol": "BTC-KRW",
            "timeframe": "1d",
            "timeframe_mapping": {"trend": "1d", "entry": "1d"},
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
            "params": {
                "breakout_entry_length": 20,
                "breakout_exit_length": 10,
                "trend_ma_length": 200,
                "trend_slope_lookback": 20,
                "atr_stop_multiple": 2.0,
            },
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["strategy_id"] == "turtle_spot_long_v2"
    assert payload["timeframe_mapping"]["trend"] == "1d"


def test_turtle_spot_long_v2_walkforward_api(api_client) -> None:
    response = api_client.post(
        "/walkforward/run",
        json={
            "strategy_id": "turtle_spot_long_v2",
            "symbol": "ETH-KRW",
            "timeframe": "1d",
            "timeframe_mapping": {"trend": "1d", "entry": "1d"},
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
    assert payload["strategy_id"] == "turtle_spot_long_v2"
    assert payload["segments"]


def test_turtle_spot_long_v2_sweep_compatibility(api_client) -> None:
    response = api_client.post(
        "/sweeps/run",
        json={
            "strategy_id": "turtle_spot_long_v2",
            "symbol": "SOL-KRW",
            "timeframe": "1d",
            "timeframe_mapping": {"trend": "1d", "entry": "1d"},
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
            "use_job": False,
            "sweep_space": {
                "breakout_entry_length": [20, 30, 55],
                "breakout_exit_length": [10, 11],
                "atr_stop_multiple": [1.5, 2.0],
                "trend_slope_lookback": [10, 20],
            },
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["strategy_id"] == "turtle_spot_long_v2"
    assert payload["total_combinations"] == 24
    assert payload["completed_combinations"] + payload["failed_combinations"] == 24


def test_strategy_metadata_exposes_spot_long_only(api_client) -> None:
    response = api_client.get("/strategies/turtle_spot_long_v2")
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "multi_timeframe"
    assert body["spot_long_only"] is True
    assert body["required_roles"] == ["trend", "entry"]
    assert "setup" in body["optional_roles"]
    assert body["default_timeframe_mapping"]["trend"] == "1d"
