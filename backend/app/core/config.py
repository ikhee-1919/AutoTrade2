from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    backend_dir: Path = Path(__file__).resolve().parents[2]
    project_root: Path = Path(__file__).resolve().parents[3]

    @property
    def sample_data_dir(self) -> Path:
        return self.project_root / "data" / "sample"

    @property
    def strategy_params_file(self) -> Path:
        return self.backend_dir / "app" / "data" / "strategy_params.json"

    @property
    def backtest_runs_file(self) -> Path:
        return self.backend_dir / "app" / "data" / "backtest_runs.json"

    @property
    def backtest_jobs_file(self) -> Path:
        return self.backend_dir / "app" / "data" / "backtest_jobs.json"

    @property
    def market_data_index_file(self) -> Path:
        return self.backend_dir / "app" / "data" / "market_data_datasets.json"

    @property
    def collected_market_data_dir(self) -> Path:
        return self.project_root / "data" / "market"

    @property
    def walkforward_runs_file(self) -> Path:
        return self.backend_dir / "app" / "data" / "walkforward_runs.json"

    @property
    def sweep_runs_file(self) -> Path:
        return self.backend_dir / "app" / "data" / "sweep_runs.json"

    @property
    def max_concurrent_backtest_jobs(self) -> int:
        return 2


settings = Settings()
