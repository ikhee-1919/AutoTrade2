from __future__ import annotations

from datetime import date
from datetime import datetime, timedelta
from pathlib import Path
import sys
import time

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api import dependencies
from app.backtest.engine import BacktestEngine
from app.data_collectors.base import HistoricalCandleCollector
from app.data.providers.csv_provider import CSVDataProvider
from app.repositories.backtest_job_repository import BacktestJobRepository
from app.repositories.backtest_run_repository import BacktestRunRepository
from app.repositories.market_data_repository import MarketDataRepository
from app.repositories.sweep_run_repository import SweepRunRepository
from app.repositories.walkforward_run_repository import WalkforwardRunRepository
from app.repositories.strategy_params_repository import StrategyParamsRepository
from app.repositories.top10_universe_repository import Top10UniverseRepository
from app.schemas.backtest import BacktestRunRequest
from app.services.backtest_job_service import BacktestJobService
from app.services.backtest_service import BacktestService
from app.services.chart_service import ChartService
from app.services.market_cap_provider import RankedCoin
from app.services.market_data_job_service import MarketDataJobService
from app.services.market_data_service import MarketDataService
from app.services.parameter_sweep_job_service import ParameterSweepJobService
from app.services.parameter_sweep_service import ParameterSweepService
from app.services.regime_analysis_service import RegimeAnalysisService
from app.services.regime_classifier import RegimeClassifier
from app.services.strategy_service import StrategyService
from app.services.top10_universe_service import Top10UniverseService
from app.services.walkforward_job_service import WalkforwardJobService
from app.services.walkforward_service import WalkforwardService
from app.strategy.registry import StrategyRegistry
from main import app


class SlowBacktestService(BacktestService):
    def run(self, *args, **kwargs):  # type: ignore[override]
        time.sleep(0.25)
        return super().run(*args, **kwargs)


class FakeCollector(HistoricalCandleCollector):
    def fetch_markets(self) -> list[str]:
        return [
            "KRW-BTC",
            "KRW-ETH",
            "KRW-SOL",
            "KRW-XRP",
            "KRW-ADA",
            "KRW-DOGE",
            "KRW-DOT",
            "KRW-LINK",
            "KRW-TRX",
            "KRW-AVAX",
            "KRW-MATIC",
            "USDT-BTC",
        ]

    def fetch_ohlcv(self, symbol, timeframe, start_date, end_date, progress_callback=None):  # type: ignore[override]
        current = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date, datetime.min.time())
        delta = timedelta(days=1)
        if timeframe == "1s":
            delta = timedelta(seconds=1)
        if timeframe.endswith("m"):
            delta = timedelta(minutes=int(timeframe[:-1]))
        elif timeframe == "1w":
            delta = timedelta(days=7)
        elif timeframe == "1mo":
            delta = timedelta(days=30)
        elif timeframe == "1y":
            delta = timedelta(days=365)
        rows = []
        idx = 0
        while current <= end_dt:
            price = 100 + idx
            rows.append(
                type(
                    "Obj",
                    (),
                    {
                        "timestamp": current,
                        "open": price,
                        "high": price + 1,
                        "low": price - 1,
                        "close": price + 0.5,
                        "volume": 10 + idx,
                    },
                )()
            )
            idx += 1
            current += delta
        if progress_callback:
            progress_callback(100)
        return rows


class FakeMarketCapProvider:
    def fetch_ranked_coins(self, max_items: int = 400):  # type: ignore[override]
        coins = [
            ("bitcoin", "BTC", 1_000_000_000_000, 1),
            ("ethereum", "ETH", 500_000_000_000, 2),
            ("solana", "SOL", 100_000_000_000, 3),
            ("xrp", "XRP", 90_000_000_000, 4),
            ("cardano", "ADA", 70_000_000_000, 5),
            ("dogecoin", "DOGE", 60_000_000_000, 6),
            ("polkadot", "DOT", 50_000_000_000, 7),
            ("chainlink", "LINK", 45_000_000_000, 8),
            ("tron", "TRX", 40_000_000_000, 9),
            ("avalanche-2", "AVAX", 35_000_000_000, 10),
            ("matic-network", "MATIC", 30_000_000_000, 11),
        ]
        return [
            RankedCoin(coin_id=cid, symbol=sym, name=sym, market_cap=float(cap), rank=rank)
            for cid, sym, cap, rank in coins[:max_items]
        ]


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _sample_dir() -> Path:
    return _project_root() / "data" / "sample"


@pytest.fixture
def service_bundle(tmp_path: Path):
    params_repo = StrategyParamsRepository(tmp_path / "strategy_params.json")
    run_repo = BacktestRunRepository(tmp_path / "backtest_runs.json")
    walkforward_repo = WalkforwardRunRepository(tmp_path / "walkforward_runs.json")
    sweep_repo = SweepRunRepository(tmp_path / "sweep_runs.json")
    market_repo = MarketDataRepository(
        index_file=tmp_path / "market_data_datasets.json",
        market_root=tmp_path / "market",
    )
    strategy_service = StrategyService(registry=StrategyRegistry(), params_repo=params_repo)
    backtest_service = BacktestService(
        strategy_service=strategy_service,
        data_provider=CSVDataProvider(_sample_dir()),
        run_repository=run_repo,
        engine=BacktestEngine(),
        project_root=str(_project_root()),
    )
    walkforward_service = WalkforwardService(
        strategy_service=strategy_service,
        data_provider=CSVDataProvider(_sample_dir()),
        backtest_service=backtest_service,
        walkforward_repository=walkforward_repo,
        project_root=str(_project_root()),
    )
    market_data_service = MarketDataService(
        collector=FakeCollector(),
        repository=market_repo,
        project_root=str(_project_root()),
    )
    top10_repo = Top10UniverseRepository(
        current_file=tmp_path / "universes" / "upbit_top10_marketcap" / "current.json",
        snapshots_dir=tmp_path / "universes" / "upbit_top10_marketcap" / "snapshots",
    )
    top10_service = Top10UniverseService(
        collector=FakeCollector(),
        market_data_service=market_data_service,
        repository=top10_repo,
        market_cap_provider=FakeMarketCapProvider(),
    )
    sweep_service = ParameterSweepService(
        strategy_service=strategy_service,
        backtest_service=backtest_service,
        sweep_repository=sweep_repo,
        project_root=str(_project_root()),
    )
    chart_service = ChartService(
        data_provider=CSVDataProvider(_sample_dir()),
        run_repository=run_repo,
    )
    regime_service = RegimeAnalysisService(
        data_provider=CSVDataProvider(_sample_dir()),
        classifier=RegimeClassifier(),
    )
    return {
        "strategy_service": strategy_service,
        "backtest_service": backtest_service,
        "walkforward_service": walkforward_service,
        "market_data_service": market_data_service,
        "sweep_service": sweep_service,
        "run_repo": run_repo,
        "walkforward_repo": walkforward_repo,
        "market_repo": market_repo,
        "sweep_repo": sweep_repo,
        "top10_service": top10_service,
        "regime_service": regime_service,
    }


@pytest.fixture
def api_client(tmp_path: Path):
    params_repo = StrategyParamsRepository(tmp_path / "strategy_params.json")
    run_repo = BacktestRunRepository(tmp_path / "backtest_runs.json")
    job_repo = BacktestJobRepository(tmp_path / "backtest_jobs.json")
    walkforward_repo = WalkforwardRunRepository(tmp_path / "walkforward_runs.json")
    sweep_repo = SweepRunRepository(tmp_path / "sweep_runs.json")
    market_repo = MarketDataRepository(
        index_file=tmp_path / "market_data_datasets.json",
        market_root=tmp_path / "market",
    )

    strategy_service = StrategyService(registry=StrategyRegistry(), params_repo=params_repo)
    backtest_service = SlowBacktestService(
        strategy_service=strategy_service,
        data_provider=CSVDataProvider(_sample_dir()),
        run_repository=run_repo,
        engine=BacktestEngine(),
        project_root=str(_project_root()),
    )
    job_service = BacktestJobService(
        backtest_service=backtest_service,
        job_repo=job_repo,
        max_concurrent_jobs=1,
    )
    walkforward_service = WalkforwardService(
        strategy_service=strategy_service,
        data_provider=CSVDataProvider(_sample_dir()),
        backtest_service=backtest_service,
        walkforward_repository=walkforward_repo,
        project_root=str(_project_root()),
    )
    walkforward_job_service = WalkforwardJobService(
        walkforward_service=walkforward_service,
        job_repo=job_repo,
        max_concurrent_jobs=1,
    )
    market_data_service = MarketDataService(
        collector=FakeCollector(),
        repository=market_repo,
        project_root=str(_project_root()),
    )
    top10_repo = Top10UniverseRepository(
        current_file=tmp_path / "universes" / "upbit_top10_marketcap" / "current.json",
        snapshots_dir=tmp_path / "universes" / "upbit_top10_marketcap" / "snapshots",
    )
    top10_service = Top10UniverseService(
        collector=FakeCollector(),
        market_data_service=market_data_service,
        repository=top10_repo,
        market_cap_provider=FakeMarketCapProvider(),
    )
    market_data_job_service = MarketDataJobService(
        market_data_service=market_data_service,
        top10_universe_service=top10_service,
        job_repo=job_repo,
        max_concurrent_jobs=1,
    )
    sweep_service = ParameterSweepService(
        strategy_service=strategy_service,
        backtest_service=backtest_service,
        sweep_repository=sweep_repo,
        project_root=str(_project_root()),
    )
    sweep_job_service = ParameterSweepJobService(
        sweep_service=sweep_service,
        job_repo=job_repo,
        max_concurrent_jobs=1,
    )
    chart_service = ChartService(
        data_provider=CSVDataProvider(_sample_dir()),
        run_repository=run_repo,
    )
    regime_service = RegimeAnalysisService(
        data_provider=CSVDataProvider(_sample_dir()),
        classifier=RegimeClassifier(),
    )

    app.dependency_overrides[dependencies.get_strategy_service] = lambda: strategy_service
    app.dependency_overrides[dependencies.get_backtest_service] = lambda: backtest_service
    app.dependency_overrides[dependencies.get_backtest_job_service] = lambda: job_service
    app.dependency_overrides[dependencies.get_walkforward_service] = lambda: walkforward_service
    app.dependency_overrides[dependencies.get_walkforward_job_service] = lambda: walkforward_job_service
    app.dependency_overrides[dependencies.get_market_data_service] = lambda: market_data_service
    app.dependency_overrides[dependencies.get_market_data_job_service] = lambda: market_data_job_service
    app.dependency_overrides[dependencies.get_top10_universe_service] = lambda: top10_service
    app.dependency_overrides[dependencies.get_parameter_sweep_service] = lambda: sweep_service
    app.dependency_overrides[dependencies.get_parameter_sweep_job_service] = lambda: sweep_job_service
    app.dependency_overrides[dependencies.get_chart_service] = lambda: chart_service
    app.dependency_overrides[dependencies.get_regime_analysis_service] = lambda: regime_service

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
def sample_request() -> BacktestRunRequest:
    return BacktestRunRequest(
        strategy_id="ma_regime_v1",
        symbol="BTC-KRW",
        timeframe="1d",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
    )
