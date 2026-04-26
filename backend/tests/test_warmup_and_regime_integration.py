from datetime import date
from datetime import datetime, timedelta

from app.backtest.engine import BacktestEngine, BacktestExecutionConfig
from app.models.candle import Candle
from app.schemas.backtest import BacktestRunRequest
from app.schemas.walkforward import WalkforwardRunRequest
from app.strategy.samples.mtf_confluence_pullback_v2 import MTFConfluencePullbackV2Strategy


def test_backtest_uses_indicator_history_and_trade_window(service_bundle) -> None:
    backtest_service = service_bundle["backtest_service"]
    result = backtest_service.run(
        BacktestRunRequest(
            strategy_id="mtf_confluence_pullback_v2",
            symbol="BTC-KRW",
            timeframe="1d",
            timeframe_mapping={
                "regime": "1d",
                "trend": "1d",
                "setup": "1d",
                "trigger": "1d",
            },
            start_date=date(2025, 8, 1),
            end_date=date(2025, 12, 31),
        )
    )

    assert result["indicator_start"] < result["trade_start"]
    assert result["warmup_start"] == result["indicator_start"]
    assert result["trade_start"] == date(2025, 8, 1)
    assert result["trade_end"] == date(2025, 12, 31)

    summary = result["summary"]
    diagnostics = result["diagnostics"]
    assert "insufficient_regime_history_count" in summary
    assert "regime_segment_summaries" in summary
    assert "above_200_days" in summary
    assert "below_200_days" in summary
    assert "insufficient_regime_history_count" in diagnostics


def test_insufficient_regime_history_only_when_regime_role_truly_short() -> None:
    strategy = MTFConfluencePullbackV2Strategy()
    params = strategy.default_params() | {
        "setup_rsi_min": 0.0,
        "setup_rsi_max": 100.0,
        "entry_volume_multiplier": 1.0,
        "max_distance_from_setup_ema_pct": 100.0,
        "max_trigger_atr_extension": 100.0,
        "min_stop_pct": 0.1,
        "max_stop_pct": 50.0,
        "entry_score_threshold": 0.0,
    }

    base = datetime(2025, 1, 1)

    def mk(count: int, step_minutes: int) -> list[Candle]:
        rows: list[Candle] = []
        price = 100.0
        for i in range(count):
            price += 0.05
            rows.append(
                Candle(
                    timestamp=base + timedelta(minutes=step_minutes * i),
                    open=price * 0.995,
                    high=price * 1.005,
                    low=price * 0.995,
                    close=price,
                    volume=1000 + i,
                )
            )
        return rows

    entry = mk(600, 15)
    trend = mk(300, 60)
    setup = mk(300, 60)
    trigger = mk(600, 15)
    regime = mk(80, 24 * 60)  # intentionally short for SMA200 regime history

    engine = BacktestEngine()
    result = engine.run(
        candles=entry,
        strategy=strategy,
        params=params,
        execution=BacktestExecutionConfig(),
        timeframe_bundle={
            "symbol": "KRW-BTC",
            "mapping": {"regime": "1d", "trend": "1h", "setup": "1h", "trigger": "15m"},
            "candles_by_role": {
                "regime": regime,
                "trend": trend,
                "setup": setup,
                "trigger": trigger,
                "entry": entry,
            },
            "metadata_by_role": {},
        },
        trade_start_at=entry[0].timestamp,
    )

    assert result["summary"]["insufficient_regime_history_count"] > 0


def test_walkforward_contains_warmup_and_regime_metadata(service_bundle) -> None:
    walkforward_service = service_bundle["walkforward_service"]
    result = walkforward_service.run(
        WalkforwardRunRequest(
            strategy_id="mtf_confluence_pullback_v2",
            symbol="ETH-KRW",
            timeframe="1d",
            timeframe_mapping={
                "regime": "1d",
                "trend": "1d",
                "setup": "1d",
                "trigger": "1d",
            },
            start_date=date(2025, 6, 1),
            end_date=date(2025, 12, 31),
            train_window_size=120,
            test_window_size=30,
            step_size=30,
            window_unit="candles",
        )
    )

    assert result["indicator_start"] < result["requested_period"]["start_date"]
    assert result["warmup_start"] == result["indicator_start"]
    assert "insufficient_regime_history_count" in result["summary"]
    assert "regime_counts" in result["diagnostics"]
    assert result["segments"]
    assert "regime_counts" in result["segments"][0]
