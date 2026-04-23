from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.backtest import BacktestExecutionConfig

WindowUnit = Literal["candles", "days"]
WalkforwardMode = Literal["rolling", "anchored"]
WalkforwardJobStatus = Literal["queued", "running", "completed", "failed", "cancelled"]


class WalkforwardRunRequest(BaseModel):
    strategy_id: str
    symbol: str
    timeframe: str = Field(default="1d")
    timeframe_mapping: dict[str, str] | None = None
    start_date: date
    end_date: date
    train_window_size: int = Field(default=120, ge=10)
    test_window_size: int = Field(default=30, ge=5)
    step_size: int = Field(default=30, ge=1)
    window_unit: WindowUnit = "candles"
    walkforward_mode: WalkforwardMode = "rolling"
    params: dict[str, Any] | None = None
    fee_rate: float = 0.0005
    entry_fee_rate: float | None = None
    exit_fee_rate: float | None = None
    apply_fee_on_entry: bool = True
    apply_fee_on_exit: bool = True
    slippage_rate: float = 0.0003
    entry_slippage_rate: float | None = None
    exit_slippage_rate: float | None = None
    execution_policy: Literal["next_open", "signal_close"] = "next_open"
    benchmark_enabled: bool = True
    run_tag: str | None = None
    note: str | None = None


class WalkforwardSegmentResult(BaseModel):
    segment_index: int
    train_start: date
    train_end: date
    test_start: date
    test_end: date
    linked_run_id: str | None = None
    status: str = "completed"
    trade_count: int
    gross_return_pct: float
    net_return_pct: float
    max_drawdown: float
    win_rate: float
    benchmark_buy_and_hold_return_pct: float
    excess_return_pct: float
    timeframe_mapping: dict[str, str] | None = None


class WalkforwardSummary(BaseModel):
    segment_count: int
    completed_segment_count: int
    total_net_return_pct: float
    average_segment_return_pct: float
    median_segment_return_pct: float
    worst_segment_return_pct: float
    best_segment_return_pct: float
    average_max_drawdown: float
    total_trade_count: int
    benchmark_comparison_summary: str | None = None


class WalkforwardDiagnostics(BaseModel):
    profitable_segments: int
    losing_segments: int
    segments_beating_benchmark: int
    segments_underperforming_benchmark: int


class WalkforwardRunResponse(BaseModel):
    walkforward_run_id: str
    rerun_of_walkforward_run_id: str | None = None
    request_hash: str
    created_at: datetime
    strategy_id: str
    strategy_version: str
    code_version: str
    symbol: str
    timeframe: str
    timeframe_mapping: dict[str, str] | None = None
    requested_period: dict[str, date]
    train_window_size: int
    test_window_size: int
    step_size: int
    window_unit: WindowUnit
    walkforward_mode: WalkforwardMode
    execution_config: BacktestExecutionConfig
    params_snapshot: dict[str, Any]
    benchmark_enabled: bool
    run_tag: str | None = None
    note: str | None = None
    segments: list[WalkforwardSegmentResult]
    summary: WalkforwardSummary
    diagnostics: WalkforwardDiagnostics
    interpretation_summary: str


class WalkforwardListItem(BaseModel):
    walkforward_run_id: str
    created_at: datetime
    strategy_id: str
    strategy_version: str
    symbol: str
    timeframe: str
    timeframe_mapping: dict[str, str] | None = None
    requested_period: dict[str, date]
    walkforward_mode: WalkforwardMode
    segment_count: int
    completed_segment_count: int
    total_net_return_pct: float
    average_segment_return_pct: float
    profitable_segments: int
    segments_beating_benchmark: int


class WalkforwardListResponse(BaseModel):
    items: list[WalkforwardListItem]


class WalkforwardCompareItem(BaseModel):
    walkforward_run_id: str
    created_at: datetime
    strategy_id: str
    symbol: str
    timeframe_mapping: dict[str, str] | None = None
    timeframe_mapping_summary: str | None = None
    walkforward_mode: WalkforwardMode
    segment_count: int
    total_net_return_pct: float
    average_segment_return_pct: float
    worst_segment_return_pct: float
    best_segment_return_pct: float
    segments_beating_benchmark: int
    profitable_segments: int


class WalkforwardCompareResponse(BaseModel):
    compared_count: int
    best_walkforward_run_id: str
    items: list[WalkforwardCompareItem]


class WalkforwardBatchRunRequest(BaseModel):
    strategy_id: str
    symbols: list[str] = Field(min_length=1)
    timeframe: str = Field(default="1d")
    timeframe_mapping: dict[str, str] | None = None
    start_date: date
    end_date: date
    train_window_size: int = Field(default=120, ge=10)
    test_window_size: int = Field(default=30, ge=5)
    step_size: int = Field(default=30, ge=1)
    window_unit: WindowUnit = "candles"
    walkforward_modes: list[WalkforwardMode] = Field(default_factory=lambda: ["rolling"])
    params: dict[str, Any] | None = None
    fee_rate: float = 0.0005
    entry_fee_rate: float | None = None
    exit_fee_rate: float | None = None
    apply_fee_on_entry: bool = True
    apply_fee_on_exit: bool = True
    slippage_rate: float = 0.0003
    entry_slippage_rate: float | None = None
    exit_slippage_rate: float | None = None
    execution_policy: Literal["next_open", "signal_close"] = "next_open"
    benchmark_enabled: bool = True
    use_jobs: bool = True


class WalkforwardBatchItem(BaseModel):
    symbol: str
    walkforward_mode: WalkforwardMode
    status: str
    job_id: str | None = None
    walkforward_run_id: str | None = None


class WalkforwardBatchRunResponse(BaseModel):
    batch_id: str
    created_at: datetime
    total_requested: int
    items: list[WalkforwardBatchItem]


class WalkforwardJobResponse(BaseModel):
    job_id: str
    job_type: str = "walkforward"
    status: WalkforwardJobStatus
    progress: float
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_seconds: float | None = None
    related_walkforward_run_id: str | None = None
    error_summary: str | None = None
    error_detail: str | None = None
    retry_count: int = 0
    parent_job_id: str | None = None
    request_hash: str
    duplicate_of_job_id: str | None = None
    segment_total: int | None = None
    segment_completed: int | None = None
    failed_segment_index: int | None = None
    request: WalkforwardRunRequest


class WalkforwardJobListResponse(BaseModel):
    items: list[WalkforwardJobResponse]
