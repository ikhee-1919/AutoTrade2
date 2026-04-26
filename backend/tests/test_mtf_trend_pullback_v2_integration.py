def test_mtf_pullback_v2_backtest_api(api_client) -> None:
    response = api_client.post(
        "/backtests/run",
        json={
            "strategy_id": "mtf_trend_pullback_v2",
            "symbol": "BTC-KRW",
            "timeframe": "1d",
            "timeframe_mapping": {"trend": "1d", "setup": "1d", "entry": "1d"},
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["strategy_id"] == "mtf_trend_pullback_v2"
    assert body["timeframe_mapping"]["trend"] == "1d"
    assert "reject_reason_counts" in body["diagnostics"]


def test_mtf_pullback_v2_walkforward_api(api_client) -> None:
    response = api_client.post(
        "/walkforward/run",
        json={
            "strategy_id": "mtf_trend_pullback_v2",
            "symbol": "ETH-KRW",
            "timeframe": "1d",
            "timeframe_mapping": {"trend": "1d", "setup": "1d", "entry": "1d"},
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
            "train_window_size": 120,
            "test_window_size": 30,
            "step_size": 30,
            "window_unit": "candles",
            "walkforward_mode": "rolling",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["strategy_id"] == "mtf_trend_pullback_v2"
    assert body["segments"]
    assert body["timeframe_mapping"]["entry"] == "1d"


def test_mtf_pullback_v2_sweep_compatibility(api_client) -> None:
    response = api_client.post(
        "/sweeps/run",
        json={
            "strategy_id": "mtf_trend_pullback_v2",
            "symbol": "SOL-KRW",
            "timeframe": "1d",
            "timeframe_mapping": {"trend": "1d", "setup": "1d", "entry": "1d"},
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
            "use_job": False,
            "sweep_space": {
                "setup_rsi_min": [38, 40],
                "setup_rsi_max": [60],
                "entry_volume_multiplier": [1.0, 1.1],
                "max_distance_from_60m_ema20_pct": [2.0],
                "max_atr_extension": [1.3],
                "atr_stop_mult": [1.6],
                "min_stop_pct": [0.8],
                "max_stop_pct": [3.0],
                "regime_reversal_confirm_bars": [2],
                "after_stop_loss_hours": [12],
            },
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["strategy_id"] == "mtf_trend_pullback_v2"
    assert body["total_combinations"] == 4
    assert body["completed_combinations"] + body["failed_combinations"] == 4


def test_mtf_pullback_v2_strategy_metadata(api_client) -> None:
    response = api_client.get("/strategies/mtf_trend_pullback_v2")
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "multi_timeframe"
    assert body["required_roles"] == ["trend", "setup", "entry"]
    assert body["default_timeframe_mapping"] == {"trend": "1d", "setup": "60m", "entry": "15m"}

