def test_mtf_confluence_v2_backtest_api(api_client) -> None:
    response = api_client.post(
        "/backtests/run",
        json={
            "strategy_id": "mtf_confluence_pullback_v2",
            "symbol": "BTC-KRW",
            "timeframe": "1d",
            "timeframe_mapping": {
                "regime": "1d",
                "trend": "1d",
                "setup": "1d",
                "confirmation": "1d",
                "trigger": "1d",
                "execution": "1d",
            },
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["strategy_id"] == "mtf_confluence_pullback_v2"
    assert body["timeframe_mapping"]["trigger"] == "1d"
    assert "reject_reason_counts" in body["diagnostics"]
    assert body["indicator_start"] <= body["trade_start"]
    assert body["trade_start"] == body["start_date"]
    assert body["trade_end"] == body["end_date"]


def test_mtf_confluence_v2_walkforward_api(api_client) -> None:
    response = api_client.post(
        "/walkforward/run",
        json={
            "strategy_id": "mtf_confluence_pullback_v2",
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
    assert body["strategy_id"] == "mtf_confluence_pullback_v2"
    assert body["segments"]
    assert body["timeframe_mapping"]["trigger"] == "1d"
    assert body["indicator_start"] <= body["requested_period"]["start_date"]
    assert "insufficient_regime_history_count" in body["summary"]


def test_mtf_confluence_v2_sweep_compatibility(api_client) -> None:
    response = api_client.post(
        "/sweeps/run",
        json={
            "strategy_id": "mtf_confluence_pullback_v2",
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
                "max_distance_from_setup_ema_pct": [2.0, 2.5],
                "max_trigger_atr_extension": [1.3],
                "atr_stop_mult": [1.6, 1.8],
                "min_stop_pct": [0.8],
                "max_stop_pct": [3.0],
                "trend_exit_confirm_bars": [2],
                "after_stop_loss_hours": [12],
                "entry_volume_multiplier": [1.0],
                "setup_rsi_min": [38],
                "setup_rsi_max": [62],
                "entry_score_threshold": [65],
            },
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["strategy_id"] == "mtf_confluence_pullback_v2"
    assert body["total_combinations"] == 4
    assert body["completed_combinations"] + body["failed_combinations"] == 4


def test_mtf_confluence_v2_strategy_metadata(api_client) -> None:
    response = api_client.get("/strategies/mtf_confluence_pullback_v2")
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "multi_timeframe"
    assert body["spot_long_only"] is True
    assert body["required_roles"] == ["regime", "trend", "setup", "trigger"]
    assert body["optional_roles"] == ["confirmation", "execution"]
    assert body["default_timeframe_mapping"] == {
        "regime": "1d",
        "trend": "4h",
        "setup": "1h",
        "confirmation": "30m",
        "trigger": "15m",
        "execution": "5m",
    }
