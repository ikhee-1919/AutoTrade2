from functools import lru_cache

from app.backtest.engine import BacktestEngine
from app.core.config import settings
from app.data_collectors.upbit_collector import UpbitHistoricalCollector
from app.data.providers.csv_provider import CSVDataProvider
from app.repositories.market_data_repository import MarketDataRepository
from app.repositories.backtest_run_repository import BacktestRunRepository
from app.repositories.backtest_job_repository import BacktestJobRepository
from app.repositories.sweep_run_repository import SweepRunRepository
from app.repositories.walkforward_run_repository import WalkforwardRunRepository
from app.repositories.strategy_params_repository import StrategyParamsRepository
from app.services.backtest_job_service import BacktestJobService
from app.services.backtest_service import BacktestService
from app.services.market_data_job_service import MarketDataJobService
from app.services.market_data_service import MarketDataService
from app.services.parameter_sweep_job_service import ParameterSweepJobService
from app.services.parameter_sweep_service import ParameterSweepService
from app.services.signal_service import SignalService
from app.services.strategy_service import StrategyService
from app.services.symbol_service import SymbolService
from app.services.walkforward_job_service import WalkforwardJobService
from app.services.walkforward_service import WalkforwardService
from app.strategy.registry import StrategyRegistry


@lru_cache
def get_strategy_registry() -> StrategyRegistry:
    return StrategyRegistry()


@lru_cache
def get_strategy_params_repo() -> StrategyParamsRepository:
    return StrategyParamsRepository(settings.strategy_params_file)


@lru_cache
def get_backtest_runs_repo() -> BacktestRunRepository:
    return BacktestRunRepository(settings.backtest_runs_file)


@lru_cache
def get_backtest_jobs_repo() -> BacktestJobRepository:
    return BacktestJobRepository(settings.backtest_jobs_file)


@lru_cache
def get_walkforward_runs_repo() -> WalkforwardRunRepository:
    return WalkforwardRunRepository(settings.walkforward_runs_file)


@lru_cache
def get_sweep_runs_repo() -> SweepRunRepository:
    return SweepRunRepository(settings.sweep_runs_file)


@lru_cache
def get_data_provider() -> CSVDataProvider:
    return CSVDataProvider(
        sample_data_dir=settings.sample_data_dir,
        collected_data_dir=settings.collected_market_data_dir,
    )


@lru_cache
def get_market_data_repository() -> MarketDataRepository:
    return MarketDataRepository(
        index_file=settings.market_data_index_file,
        market_root=settings.collected_market_data_dir,
    )


@lru_cache
def get_upbit_collector() -> UpbitHistoricalCollector:
    return UpbitHistoricalCollector()


@lru_cache
def get_market_data_service() -> MarketDataService:
    return MarketDataService(
        collector=get_upbit_collector(),
        repository=get_market_data_repository(),
        project_root=str(settings.project_root),
    )


@lru_cache
def get_market_data_job_service() -> MarketDataJobService:
    return MarketDataJobService(
        market_data_service=get_market_data_service(),
        job_repo=get_backtest_jobs_repo(),
        max_concurrent_jobs=settings.max_concurrent_backtest_jobs,
    )


@lru_cache
def get_strategy_service() -> StrategyService:
    return StrategyService(
        registry=get_strategy_registry(),
        params_repo=get_strategy_params_repo(),
    )


@lru_cache
def get_backtest_service() -> BacktestService:
    return BacktestService(
        strategy_service=get_strategy_service(),
        data_provider=get_data_provider(),
        run_repository=get_backtest_runs_repo(),
        engine=BacktestEngine(),
        project_root=str(settings.project_root),
    )


@lru_cache
def get_backtest_job_service() -> BacktestJobService:
    return BacktestJobService(
        backtest_service=get_backtest_service(),
        job_repo=get_backtest_jobs_repo(),
        max_concurrent_jobs=settings.max_concurrent_backtest_jobs,
    )


@lru_cache
def get_walkforward_service() -> WalkforwardService:
    return WalkforwardService(
        strategy_service=get_strategy_service(),
        data_provider=get_data_provider(),
        backtest_service=get_backtest_service(),
        walkforward_repository=get_walkforward_runs_repo(),
        project_root=str(settings.project_root),
    )


@lru_cache
def get_walkforward_job_service() -> WalkforwardJobService:
    return WalkforwardJobService(
        walkforward_service=get_walkforward_service(),
        job_repo=get_backtest_jobs_repo(),
        max_concurrent_jobs=settings.max_concurrent_backtest_jobs,
    )


@lru_cache
def get_parameter_sweep_service() -> ParameterSweepService:
    return ParameterSweepService(
        strategy_service=get_strategy_service(),
        backtest_service=get_backtest_service(),
        sweep_repository=get_sweep_runs_repo(),
        project_root=str(settings.project_root),
    )


@lru_cache
def get_parameter_sweep_job_service() -> ParameterSweepJobService:
    return ParameterSweepJobService(
        sweep_service=get_parameter_sweep_service(),
        job_repo=get_backtest_jobs_repo(),
        max_concurrent_jobs=1,
    )


@lru_cache
def get_symbol_service() -> SymbolService:
    return SymbolService(data_provider=get_data_provider())


@lru_cache
def get_signal_service() -> SignalService:
    return SignalService(
        strategy_service=get_strategy_service(),
        data_provider=get_data_provider(),
    )
