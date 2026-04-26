def test_recovery_v1_backtest_api(api_client) -> None:
    response = api_client.post(
        "/backtests/run",
        json={
            "strategy_id": "below_200_recovery_long_v1",
            "symbol": "BTC-KRW",
            "timeframe": "1d",
            "timeframe_mapping": {
                "regime": "1d",
                "trend": "1d",
                "setup": "1d",
                "trigger": "1d",
                "execution": "1d",
            },
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["strategy_id"] == "below_200_recovery_long_v1"
    assert body["timeframe_mapping"]["trigger"] == "1d"
    assert "reject_reason_counts" in body["diagnostics"]


def test_recovery_v1_walkforward_api(api_client) -> None:
    response = api_client.post(
        "/walkforward/run",
        json={
            "strategy_id": "below_200_recovery_long_v1",
            "symbol": "ETH-KRW",
            "timeframe": "1d",
            "timeframe_mapping": {
                "regime": "1d",
                "trend": "1d",
                "setup": "1d",
                "trigger": "1d",
            },
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
            "train_window_size": 240,
            "test_window_size": 60,
            "step_size": 30,
            "window_unit": "candles",
            "walkforward_mode": "rolling",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["strategy_id"] == "below_200_recovery_long_v1"
    assert body["segments"]
    assert body["timeframe_mapping"]["trigger"] == "1d"


def test_recovery_v1_sweep_compatibility(api_client) -> None:
    response = api_client.post(
        "/sweeps/run",
        json={
            "strategy_id": "below_200_recovery_long_v1",
            "symbol": "SOL-KRW",
            "timeframe": "1d",
            "timeframe_mapping": {
                "regime": "1d",
                "trend": "1d",
                "setup": "1d",
                "trigger": "1d",
            },
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
            "use_job": False,
            "sweep_space": {
                "max_distance_below_sma200_pct": [8.0, 12.0],
                "setup_rsi_min": [40.0],
                "setup_rsi_max": [60.0],
                "trigger_volume_multiplier": [1.0, 1.1],
                "atr_stop_mult": [1.4],
                "min_stop_pct": [0.7],
                "max_stop_pct": [3.0],
                "time_stop_hours": [48],
                "entry_score_threshold": [65],
                "after_stop_loss_hours": [12],
            },
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["strategy_id"] == "below_200_recovery_long_v1"
    assert body["total_combinations"] == 4
    assert body["completed_combinations"] + body["failed_combinations"] == 4


def test_recovery_v1_strategy_metadata(api_client) -> None:
    response = api_client.get("/strategies/below_200_recovery_long_v1")
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "multi_timeframe"
    assert body["spot_long_only"] is True
    assert body["required_roles"] == ["regime", "trend", "setup", "trigger"]
    assert body["optional_roles"] == ["execution"]
    assert body["default_timeframe_mapping"] == {
        "regime": "1d",
        "trend": "4h",
        "setup": "1h",
        "trigger": "15m",
        "execution": "5m",
    }
