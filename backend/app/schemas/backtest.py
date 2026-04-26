from datetime import date, datetime
from typing import Literal
from typing import Any

from pydantic import BaseModel, Field

ExecutionPolicy = Literal["next_open", "signal_close"]


class BacktestRunRequest(BaseModel):
    strategy_id: str
    symbol: str
    timeframe: str = Field(default="1d")
    timeframe_mapping: dict[str, str] | None = None
    start_date: date
    end_date: date
    indicator_start: date | None = None
    warmup_days: int | None = Field(default=None, ge=0)
    params: dict[str, Any] | None = None
    run_tag: str | None = None
    note: str | None = None
    fee_rate: float = 0.0005
    entry_fee_rate: float | None = None
    exit_fee_rate: float | None = None
    apply_fee_on_entry: bool = True
    apply_fee_on_exit: bool = True
    slippage_rate: float = 0.0003
    entry_slippage_rate: float | None = None
    exit_slippage_rate: float | None = None
    execution_policy: ExecutionPolicy = "next_open"
    benchmark_enabled: bool = True


class BacktestSummary(BaseModel):
    total_return_pct: float
    gross_return_pct: float
    net_return_pct: float
    buy_and_hold_return_pct: float = 0.0
    excess_return_vs_buy_and_hold: float = 0.0
    trade_count: int
    win_rate: float
    max_drawdown: float
    avg_profit: float
    avg_loss: float
    profit_factor: float = 0.0
    avg_win_pct: float = 0.0
    avg_loss_pct: float = 0.0
    expectancy_per_trade: float = 0.0
    max_consecutive_losses: int = 0
    avg_holding_time: float = 0.0
    exposure_pct: float = 0.0
    total_fees_paid: float
    total_slippage_cost: float
    total_trading_cost: float
    fee_total: float = 0.0
    slippage_total: float = 0.0
    fee_impact_pct: float
    slippage_impact_pct: float
    cost_drag_pct: float
    exit_reason_counts: dict[str, int] = Field(default_factory=dict)
    reject_reason_counts: dict[str, int] = Field(default_factory=dict)
    regime_counts: dict[str, int] = Field(default_factory=dict)
    regime_segment_summaries: list[dict[str, Any]] = Field(default_factory=list)
    above_200_days: int = 0
    below_200_days: int = 0
    insufficient_regime_history_count: int = 0
    above_200_return: float = 0.0
    below_200_return: float = 0.0
    monthly_returns: list[dict[str, Any]] = Field(default_factory=list)


class BacktestTrade(BaseModel):
    entry_time: str
    exit_time: str
    side: str
    intended_entry_price: float
    filled_entry_price: float
    intended_exit_price: float
    filled_exit_price: float
    gross_pnl: float
    net_pnl: float
    fee_entry: float
    fee_exit: float
    total_fees: float
    slippage_entry_cost: float
    slippage_exit_cost: float
    total_slippage_cost: float
    total_trading_cost: float
    entry_price: float
    exit_price: float
    pnl: float
    reason: str
    gross_pnl_pct: float | None = None
    net_pnl_pct: float | None = None
    fees: float | None = None
    slippage: float | None = None
    holding_time: float = 0.0
    entry_reason: str | None = None
    exit_reason: str | None = None
    stop_price: float | None = None
    highest_price_during_trade: float | None = None
    lowest_price_during_trade: float | None = None
    r_multiple: float | None = None
    entry_signal_score: float | None = None
    exit_signal_score: float | None = None
    max_favorable_excursion_pct: float | None = None
    max_adverse_excursion_pct: float | None = None


class BacktestDiagnostics(BaseModel):
    reject_reason_counts: dict[str, int]
    regime_counts: dict[str, int]
    exit_reason_counts: dict[str, int] = Field(default_factory=dict)
    regime_segment_summaries: list[dict[str, Any]] = Field(default_factory=list)
    above_200_segments: list[dict[str, Any]] = Field(default_factory=list)
    below_200_segments: list[dict[str, Any]] = Field(default_factory=list)
    above_200_days: int = 0
    below_200_days: int = 0
    insufficient_regime_history_count: int = 0
    above_200_return: float = 0.0
    below_200_return: float = 0.0


class BacktestDataSignature(BaseModel):
    source: str
    candle_count: int
    first_timestamp: str | None = None
    last_timestamp: str | None = None
    candles_hash: str
    dataset_id: str | None = None
    dataset_signature: str | None = None


class BacktestRoleDatasetSelection(BaseModel):
    role: str
    timeframe: str
    source_type: str
    dataset_id: str | None = None
    dataset_signature: str | None = None
    quality_status: str | None = None


class BacktestExecutionConfig(BaseModel):
    execution_policy: ExecutionPolicy
    fee_rate: float
    entry_fee_rate: float
    exit_fee_rate: float
    apply_fee_on_entry: bool
    apply_fee_on_exit: bool
    slippage_rate: float
    entry_slippage_rate: float
    exit_slippage_rate: float
    benchmark_enabled: bool


class BacktestBenchmark(BaseModel):
    benchmark_buy_and_hold_return_pct: float
    strategy_excess_return_pct: float
    benchmark_start_price: float
    benchmark_end_price: float
    benchmark_curve: list[dict[str, Any]] = Field(default_factory=list)


class BacktestRunResponse(BaseModel):
    run_id: str
    rerun_of_run_id: str | None = None
    run_at: datetime
    strategy_id: str
    strategy_version: str
    code_version: str
    symbol: str
    timeframe: str
    timeframe_mapping: dict[str, str] | None = None
    indicator_start: date | None = None
    warmup_start: date | None = None
    trade_start: date
    trade_end: date
    start_date: date
    end_date: date
    params_used: dict[str, Any]
    params_snapshot: dict[str, Any]
    params_hash: str
    data_signature: BacktestDataSignature
    selected_datasets_by_role: dict[str, BacktestRoleDatasetSelection] = Field(default_factory=dict)
    execution_config: BacktestExecutionConfig
    run_tag: str | None = None
    note: str | None = None
    summary: BacktestSummary
    benchmark: BacktestBenchmark | None = None
    trades: list[BacktestTrade]
    diagnostics: BacktestDiagnostics
    equity_curve: list[dict[str, Any]] = Field(default_factory=list)


class BacktestRecentItem(BaseModel):
    run_id: str
    rerun_of_run_id: str | None = None
    run_at: datetime
    strategy_id: str
    strategy_version: str
    code_version: str
    symbol: str
    timeframe: str
    timeframe_mapping: dict[str, str] | None = None
    indicator_start: date | None = None
    warmup_start: date | None = None
    trade_start: date | None = None
    trade_end: date | None = None
    start_date: date
    end_date: date
    params_used: dict[str, Any]
    params_snapshot: dict[str, Any]
    params_hash: str
    data_signature: BacktestDataSignature
    selected_datasets_by_role: dict[str, BacktestRoleDatasetSelection] = Field(default_factory=dict)
    execution_config: BacktestExecutionConfig
    run_tag: str | None = None
    total_return_pct: float
    gross_return_pct: float
    net_return_pct: float
    total_trading_cost: float
    cost_drag_pct: float
    benchmark_buy_and_hold_return_pct: float
    strategy_excess_return_pct: float
    trade_count: int


class BacktestRecentResponse(BaseModel):
    items: list[BacktestRecentItem]


class BacktestCompareRunItem(BaseModel):
    run_id: str
    run_at: datetime
    strategy_id: str
    strategy_version: str
    code_version: str
    symbol: str
    timeframe: str
    timeframe_mapping: dict[str, str] | None = None
    timeframe_mapping_summary: str | None = None
    indicator_start: date | None = None
    warmup_start: date | None = None
    trade_start: date | None = None
    trade_end: date | None = None
    start_date: date
    end_date: date
    total_return_pct: float
    gross_return_pct: float
    net_return_pct: float
    max_drawdown: float
    win_rate: float
    trade_count: int
    summary_avg_profit: float
    summary_avg_loss: float
    profit_factor: float = 0.0
    avg_win_pct: float = 0.0
    avg_loss_pct: float = 0.0
    expectancy_per_trade: float = 0.0
    max_consecutive_losses: int = 0
    avg_holding_time: float = 0.0
    exposure_pct: float = 0.0
    total_fees_paid: float
    total_slippage_cost: float
    total_trading_cost: float
    fee_total: float = 0.0
    slippage_total: float = 0.0
    cost_drag_pct: float
    benchmark_buy_and_hold_return_pct: float
    strategy_excess_return_pct: float
    exit_reason_counts: dict[str, int] = Field(default_factory=dict)
    reject_reason_counts: dict[str, int] = Field(default_factory=dict)
    regime_counts: dict[str, int] = Field(default_factory=dict)
    above_200_days: int = 0
    below_200_days: int = 0
    insufficient_regime_history_count: int = 0
    above_200_return: float = 0.0
    below_200_return: float = 0.0
    top_reject_reason: str | None = None
    return_gap_vs_best: float
    mdd_gap_vs_best: float
    run_tag: str | None = None


class BacktestCompareResponse(BaseModel):
    compared_count: int
    best_run_id: str
    items: list[BacktestCompareRunItem]


BacktestJobStatus = Literal["queued", "running", "completed", "failed", "cancelled"]


class BacktestJobResponse(BaseModel):
    job_id: str
    job_type: str = "backtest"
    status: BacktestJobStatus
    progress: float
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_seconds: float | None = None
    related_run_id: str | None = None
    error_summary: str | None = None
    error_detail: str | None = None
    retry_count: int = 0
    parent_job_id: str | None = None
    request_hash: str
    duplicate_of_job_id: str | None = None
    request: BacktestRunRequest


class BacktestJobListResponse(BaseModel):
    items: list[BacktestJobResponse]
