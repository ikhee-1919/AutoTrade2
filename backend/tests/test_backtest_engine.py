from datetime import date
from pathlib import Path

import pytest

from app.backtest.engine import BacktestEngine, BacktestExecutionConfig
from app.data.providers.csv_provider import CSVDataProvider
from app.strategy.samples.ma_regime_strategy import MovingAverageRegimeStrategy


def _sample_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "sample"


def test_backtest_engine_summary_and_diagnostics_shape() -> None:
    provider = CSVDataProvider(_sample_dir())
    strategy = MovingAverageRegimeStrategy()
    candles = provider.load_ohlcv("BTC-KRW", "1d", date(2025, 1, 1), date(2025, 12, 31))

    engine = BacktestEngine()
    result = engine.run(
        candles=candles,
        strategy=strategy,
        params=strategy.default_params(),
        execution=BacktestExecutionConfig(
            execution_policy="next_open",
            entry_fee_rate=0.0005,
            exit_fee_rate=0.0005,
            apply_fee_on_entry=True,
            apply_fee_on_exit=True,
            entry_slippage_rate=0.0003,
            exit_slippage_rate=0.0003,
            benchmark_enabled=True,
        ),
    )

    assert "summary" in result
    assert "trades" in result
    assert "diagnostics" in result
    assert "equity_curve" in result
    assert set(result["summary"].keys()) >= {
        "total_return_pct",
        "gross_return_pct",
        "net_return_pct",
        "trade_count",
        "win_rate",
        "max_drawdown",
        "avg_profit",
        "avg_loss",
        "total_fees_paid",
        "total_slippage_cost",
        "total_trading_cost",
        "cost_drag_pct",
    }
    assert "benchmark" in result


def test_backtest_engine_invalid_input_raises() -> None:
    engine = BacktestEngine()
    strategy = MovingAverageRegimeStrategy()
    with pytest.raises(ValueError):
        engine.run(
            candles=[],
            strategy=strategy,
            params=strategy.default_params(),
            execution=BacktestExecutionConfig(
                execution_policy="signal_close",
                entry_fee_rate=0.0005,
                exit_fee_rate=0.0005,
                apply_fee_on_entry=True,
                apply_fee_on_exit=True,
                entry_slippage_rate=0.0003,
                exit_slippage_rate=0.0003,
                benchmark_enabled=True,
            ),
        )


def test_execution_policy_changes_results() -> None:
    provider = CSVDataProvider(_sample_dir())
    strategy = MovingAverageRegimeStrategy()
    candles = provider.load_ohlcv("ETH-KRW", "1d", date(2025, 1, 1), date(2025, 12, 31))

    engine = BacktestEngine()
    base = strategy.default_params()

    signal_close = engine.run(
        candles=candles,
        strategy=strategy,
        params=base,
        execution=BacktestExecutionConfig(
            execution_policy="signal_close",
            entry_fee_rate=0.0005,
            exit_fee_rate=0.0005,
            apply_fee_on_entry=True,
            apply_fee_on_exit=True,
            entry_slippage_rate=0.0003,
            exit_slippage_rate=0.0003,
            benchmark_enabled=True,
        ),
    )
    next_open = engine.run(
        candles=candles,
        strategy=strategy,
        params=base,
        execution=BacktestExecutionConfig(
            execution_policy="next_open",
            entry_fee_rate=0.0005,
            exit_fee_rate=0.0005,
            apply_fee_on_entry=True,
            apply_fee_on_exit=True,
            entry_slippage_rate=0.0003,
            exit_slippage_rate=0.0003,
            benchmark_enabled=True,
        ),
    )

    assert signal_close["summary"]["net_return_pct"] != next_open["summary"]["net_return_pct"]


def test_fee_slippage_make_net_lower_than_gross() -> None:
    provider = CSVDataProvider(_sample_dir())
    strategy = MovingAverageRegimeStrategy()
    candles = provider.load_ohlcv("SOL-KRW", "1d", date(2025, 1, 1), date(2025, 12, 31))
    engine = BacktestEngine()
    res = engine.run(
        candles=candles,
        strategy=strategy,
        params=strategy.default_params(),
        execution=BacktestExecutionConfig(
            execution_policy="next_open",
            entry_fee_rate=0.001,
            exit_fee_rate=0.001,
            apply_fee_on_entry=True,
            apply_fee_on_exit=True,
            entry_slippage_rate=0.001,
            exit_slippage_rate=0.001,
            benchmark_enabled=True,
        ),
    )

    assert res["summary"]["gross_return_pct"] >= res["summary"]["net_return_pct"] - 1e-9
    assert res["summary"]["total_trading_cost"] >= 0
    if res["trades"]:
        trade = res["trades"][0]
        assert "gross_pnl" in trade and "net_pnl" in trade
        assert "total_fees" in trade and "total_slippage_cost" in trade
