from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.backtest import BacktestExecutionConfig


class SweepRunRequest(BaseModel):
    strategy_id: str
    symbol: str
    timeframe: str = Field(default="1d")
    timeframe_mapping: dict[str, str] | None = None
    start_date: date
    end_date: date
    sweep_space: dict[str, list[float | int | str]] = Field(default_factory=dict)
    benchmark_enabled: bool = True
    fee_rate: float = 0.0005
    entry_fee_rate: float | None = None
    exit_fee_rate: float | None = None
    apply_fee_on_entry: bool = True
    apply_fee_on_exit: bool = True
    slippage_rate: float = 0.0003
    entry_slippage_rate: float | None = None
    exit_slippage_rate: float | None = None
    execution_policy: Literal["next_open", "signal_close"] = "next_open"
    use_job: bool = True
    run_tag: str | None = None
    note: str | None = None


class SweepCombinationResult(BaseModel):
    combination_id: str
    params_snapshot: dict[str, Any]
    related_run_id: str | None = None
    gross_return_pct: float = 0.0
    net_return_pct: float = 0.0
    max_drawdown: float = 0.0
    trade_count: int = 0
    win_rate: float = 0.0
    benchmark_buy_and_hold_return_pct: float = 0.0
    excess_return_pct: float = 0.0
    status: Literal["completed", "failed"]
    error_summary: str | None = None


class SweepRankingSummary(BaseModel):
    best_by_net_return: SweepCombinationResult | None = None
    best_by_excess_return: SweepCombinationResult | None = None
    lowest_drawdown_group: list[SweepCombinationResult] = Field(default_factory=list)
    top_n: list[SweepCombinationResult] = Field(default_factory=list)
    profitable_count: int = 0
    losing_count: int = 0
    average_net_return: float = 0.0
    median_net_return: float = 0.0
    average_max_drawdown: float = 0.0


class SweepRunResponse(BaseModel):
    sweep_run_id: str
    rerun_of_sweep_run_id: str | None = None
    request_hash: str
    created_at: datetime
    strategy_id: str
    strategy_version: str
    code_version: str
    symbol: str
    timeframe: str
    timeframe_mapping: dict[str, str] | None = None
    start_date: date
    end_date: date
    execution_config: BacktestExecutionConfig
    benchmark_enabled: bool
    sweep_space: dict[str, list[float | int | str]]
    total_combinations: int
    completed_combinations: int
    failed_combinations: int
    run_tag: str | None = None
    note: str | None = None
    ranking_summary: SweepRankingSummary
    results: list[SweepCombinationResult]


class SweepListItem(BaseModel):
    sweep_run_id: str
    created_at: datetime
    strategy_id: str
    strategy_version: str
    symbol: str
    timeframe: str
    timeframe_mapping: dict[str, str] | None = None
    total_combinations: int
    completed_combinations: int
    failed_combinations: int
    top_net_return_pct: float = 0.0
    average_net_return: float = 0.0


class SweepListResponse(BaseModel):
    items: list[SweepListItem]


class SweepResultsResponse(BaseModel):
    sweep_run_id: str
    total: int
    items: list[SweepCombinationResult]


class SweepTopResponse(BaseModel):
    sweep_run_id: str
    sort_by: str
    items: list[SweepCombinationResult]


SweepJobStatus = Literal["queued", "running", "completed", "failed", "cancelled"]


class SweepJobResponse(BaseModel):
    job_id: str
    job_type: str
    status: SweepJobStatus
    progress: float
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_seconds: float | None = None
    related_sweep_run_id: str | None = None
    total_combinations: int | None = None
    completed_combinations: int | None = None
    failed_combinations: int | None = None
    error_summary: str | None = None
    error_detail: str | None = None
    retry_count: int = 0
    parent_job_id: str | None = None
    request_hash: str
    duplicate_of_job_id: str | None = None
    request: SweepRunRequest


class SweepJobListResponse(BaseModel):
    items: list[SweepJobResponse]
