from datetime import date


def test_chart_candles_api_returns_rows_and_dataset(api_client) -> None:
    response = api_client.get(
        "/charts/candles",
        params={
            "symbol": "KRW-BTC",
            "timeframe": "1d",
            "start_date": "2025-01-01",
            "end_date": "2025-03-01",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["symbol"] == "KRW-BTC"
    assert body["timeframe"] == "1d"
    assert len(body["items"]) > 0
    assert {"time", "open", "high", "low", "close", "volume"}.issubset(body["items"][0].keys())
    assert body["dataset"] is not None
    assert body["dataset"]["source_type"] == "sample"


def test_chart_indicators_api_has_ema_and_rsi(api_client) -> None:
    candles = api_client.get(
        "/charts/candles",
        params={
            "symbol": "KRW-ETH",
            "timeframe": "1d",
            "start_date": "2025-01-01",
            "end_date": "2025-03-31",
        },
    )
    indicator = api_client.get(
        "/charts/indicators",
        params={
            "symbol": "KRW-ETH",
            "timeframe": "1d",
            "start_date": "2025-01-01",
            "end_date": "2025-03-31",
            "indicators": ["ema20", "ema50", "ema120", "rsi14", "volume_ma20"],
        },
    )
    assert indicator.status_code == 200
    payload = indicator.json()
    candle_len = len(candles.json()["items"])
    assert len(payload["items"]) == candle_len
    assert {"ema20", "ema50", "ema120", "rsi14", "volume_ma20"}.issubset(payload["items"][0].keys())


def test_chart_backtest_overlay_api(api_client) -> None:
    run = api_client.post(
        "/backtests/run",
        json={
            "strategy_id": "ma_regime_v1",
            "symbol": "KRW-BTC",
            "timeframe": "1d",
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
            "params": {"entry_score_threshold": 0.2},
        },
    )
    assert run.status_code == 200
    run_id = run.json()["run_id"]

    overlay = api_client.get("/charts/backtest-overlay", params={"run_id": run_id})
    assert overlay.status_code == 200
    body = overlay.json()
    assert body["run_id"] == run_id
    assert body["run_meta"]["strategy_id"] == "ma_regime_v1"
    assert "timeframe_mapping" in body["run_meta"]
    assert isinstance(body["trades"], list)
    if body["trades"]:
        first = body["trades"][0]
        assert {"entry_time", "exit_time", "entry_price", "exit_price", "gross_pct", "net_pct"}.issubset(first.keys())


def test_chart_overlay_reflects_mtf_mapping(api_client) -> None:
    run = api_client.post(
        "/backtests/run",
        json={
            "strategy_id": "trend_momentum_volume_score_v2",
            "symbol": "KRW-BTC",
            "timeframe": "5m",
            "timeframe_mapping": {"trend": "1d", "entry": "1d"},
            "start_date": date(2025, 1, 1).isoformat(),
            "end_date": date(2025, 4, 1).isoformat(),
        },
    )
    assert run.status_code == 200
    run_id = run.json()["run_id"]

    overlay = api_client.get("/charts/backtest-overlay", params={"run_id": run_id})
    assert overlay.status_code == 200
    mapping = overlay.json()["run_meta"]["timeframe_mapping"]
    assert mapping is not None
    assert mapping["trend"] == "1d"
    assert mapping["entry"] == "1d"
