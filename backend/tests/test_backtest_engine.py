from datetime import date
from datetime import datetime, timedelta
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
        "buy_and_hold_return_pct",
        "excess_return_vs_buy_and_hold",
        "trade_count",
        "win_rate",
        "max_drawdown",
        "avg_profit",
        "avg_loss",
        "profit_factor",
        "avg_win_pct",
        "avg_loss_pct",
        "expectancy_per_trade",
        "max_consecutive_losses",
        "avg_holding_time",
        "exposure_pct",
        "total_fees_paid",
        "total_slippage_cost",
        "total_trading_cost",
        "fee_total",
        "slippage_total",
        "cost_drag_pct",
        "exit_reason_counts",
        "reject_reason_counts",
        "monthly_returns",
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
    assert "exit_reason_counts" in res["summary"]
    assert "monthly_returns" in res["summary"]
    if res["trades"]:
        trade = res["trades"][0]
        assert "gross_pnl" in trade and "net_pnl" in trade
        assert "total_fees" in trade and "total_slippage_cost" in trade
        assert "holding_time" in trade and "r_multiple" in trade
        assert "max_favorable_excursion_pct" in trade


def test_core_metric_helpers() -> None:
    engine = BacktestEngine()
    assert engine._profit_factor([2.0, 1.0], [-1.0, -1.0]) == 1.5
    assert engine._max_consecutive_losses([1.0, -0.5, -0.3, 0.2, -0.1]) == 2

    start = datetime(2025, 1, 1, 0, 0, 0)
    end = datetime(2025, 1, 2, 0, 0, 0)
    trades = [
        {
            "entry_time": start.isoformat(),
            "exit_time": (start + timedelta(hours=6)).isoformat(),
        },
        {
            "entry_time": (start + timedelta(hours=12)).isoformat(),
            "exit_time": (start + timedelta(hours=18)).isoformat(),
        },
    ]
    # type: ignore[arg-type] - helper only reads entry/exit timestamps.
    exposure = engine._exposure_pct(start, end, trades)  # pyright: ignore[reportArgumentType]
    assert round(exposure, 2) == 50.0


def test_summary_buy_and_hold_and_excess_are_filled() -> None:
    provider = CSVDataProvider(_sample_dir())
    strategy = MovingAverageRegimeStrategy()
    candles = provider.load_ohlcv("BTC-KRW", "1d", date(2025, 1, 1), date(2025, 12, 31))
    engine = BacktestEngine()
    res = engine.run(
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
    assert "buy_and_hold_return_pct" in res["summary"]
    assert "excess_return_vs_buy_and_hold" in res["summary"]
    assert (
        res["summary"]["excess_return_vs_buy_and_hold"]
        == res["benchmark"]["strategy_excess_return_pct"]
    )
