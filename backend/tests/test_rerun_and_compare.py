from datetime import date

from app.schemas.backtest import BacktestRunRequest


def test_rerun_reproducibility(service_bundle) -> None:
    backtest_service = service_bundle["backtest_service"]

    first = backtest_service.run(
        request=BacktestRunRequest(
            strategy_id="ma_regime_v1",
            symbol="ETH-KRW",
            timeframe="1d",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            fee_rate=0.0007,
            slippage_rate=0.0004,
            execution_policy="signal_close",
            benchmark_enabled=False,
        ),
    )
    rerun = backtest_service.rerun(first["run_id"])

    assert first["params_hash"] == rerun["params_hash"]
    assert first["data_signature"]["candles_hash"] == rerun["data_signature"]["candles_hash"]
    assert rerun["rerun_of_run_id"] == first["run_id"]
    assert rerun["execution_config"]["fee_rate"] == first["execution_config"]["fee_rate"]
    assert rerun["execution_config"]["slippage_rate"] == first["execution_config"]["slippage_rate"]
    assert (
        rerun["execution_config"]["execution_policy"]
        == first["execution_config"]["execution_policy"]
    )
    assert (
        rerun["execution_config"]["benchmark_enabled"]
        == first["execution_config"]["benchmark_enabled"]
    )
    assert rerun["params_snapshot"]["execution_config"] == first["params_snapshot"]["execution_config"]


def test_compare_api_structure(api_client) -> None:
    payload = {
        "strategy_id": "ma_regime_v1",
        "symbol": "BTC-KRW",
        "timeframe": "1d",
        "timeframe_mapping": {"entry": "1d"},
        "start_date": "2025-01-01",
        "end_date": "2025-12-31",
    }
    r1 = api_client.post("/backtests/run", json=payload).json()
    detail = api_client.get(f"/backtests/{r1['run_id']}")
    assert detail.status_code == 200
    assert detail.json().get("timeframe_mapping", {}).get("entry") == "1d"

    payload2 = {**payload, "symbol": "SOL-KRW"}
    r2 = api_client.post("/backtests/run", json=payload2).json()

    comp = api_client.get(f"/backtests/compare?run_ids={r1['run_id']}&run_ids={r2['run_id']}")
    assert comp.status_code == 200
    body = comp.json()
    assert body["compared_count"] == 2
    assert "best_run_id" in body
    assert all("summary_avg_profit" in item for item in body["items"])
    assert all("gross_return_pct" in item for item in body["items"])
    assert all("net_return_pct" in item for item in body["items"])
    assert all("total_trading_cost" in item for item in body["items"])
    assert all("cost_drag_pct" in item for item in body["items"])
    assert all("benchmark_buy_and_hold_return_pct" in item for item in body["items"])
    assert all("strategy_excess_return_pct" in item for item in body["items"])
    assert all("timeframe_mapping" in item for item in body["items"])
