from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


QualityStatus = Literal["pass", "warning", "fail"]


class MarketDataCollectRequest(BaseModel):
    source: str = "upbit"
    symbol: str
    timeframe: str
    start_date: date
    end_date: date
    overwrite: bool = False
    dry_run: bool = False
    use_job: bool = False


class MarketDataUpdateRequest(BaseModel):
    source: str = "upbit"
    symbol: str
    timeframe: str
    end_date: date | None = None
    use_job: bool = False


class MarketDataBatchRequest(BaseModel):
    source: str = "upbit"
    symbols: list[str] = Field(min_length=1)
    timeframes: list[str] = Field(min_length=1)
    start_date: date | None = None
    end_date: date | None = None
    mode: Literal["full_collect", "incremental_update"] = "full_collect"
    validate_after_collect: bool = False
    use_job: bool = True
    overwrite: bool = False
    dry_run: bool = False


class MarketDataValidateRequest(BaseModel):
    use_job: bool = False


class MarketDataQualityReport(BaseModel):
    status: QualityStatus
    row_count: int
    duplicate_count: int
    missing_interval_count: int
    null_count: int
    invalid_ohlc_count: int
    suspicious_gap_count: int = 0
    summary_message: str
    detail_messages: list[str] = Field(default_factory=list)


class MarketDataManifest(BaseModel):
    dataset_id: str
    source: str
    exchange: str | None = None
    symbol: str
    timeframe: str
    start_at: str | None = None
    end_at: str | None = None
    row_count: int
    created_at: str
    updated_at: str
    data_signature: str
    quality_status: QualityStatus
    quality_report_summary: str
    collector_version: str = "upbit-v1"
    code_version: str = "unknown-local"
    last_checked_at: str | None = None
    path: str
    notes: str | None = None


class MarketDataDatasetItem(BaseModel):
    dataset_id: str
    source: str
    symbol: str
    timeframe: str
    start_at: str | None = None
    end_at: str | None = None
    row_count: int
    quality_status: QualityStatus
    updated_at: str


class MarketDataListResponse(BaseModel):
    items: list[MarketDataDatasetItem]


class MarketDataDetailResponse(BaseModel):
    manifest: MarketDataManifest
    quality_report: MarketDataQualityReport


class MarketDataCollectResult(BaseModel):
    dataset_id: str
    source: str
    symbol: str
    timeframe: str
    requested_period: dict[str, date]
    fetched_count: int
    saved_count: int
    duplicate_removed_count: int
    actual_range: dict[str, str | None]
    dataset_path: str
    data_signature: str
    quality_status: QualityStatus


class MarketDataOperationResponse(BaseModel):
    mode: Literal["sync", "job"]
    job_id: str | None = None
    result: MarketDataCollectResult | None = None
    message: str | None = None


class MarketDataBatchItemResult(BaseModel):
    source: str
    symbol: str
    timeframe: str
    status: Literal["completed", "failed", "skipped"]
    dataset_id: str | None = None
    quality_status: QualityStatus | None = None
    fetched_count: int = 0
    saved_count: int = 0
    message: str | None = None


class MarketDataBatchResult(BaseModel):
    mode: Literal["sync", "job"]
    batch_id: str
    total_requested_combinations: int
    completed_combinations: int
    failed_combinations: int
    skipped_combinations: int
    created_datasets: int
    updated_datasets: int
    pass_count: int
    warning_count: int
    fail_count: int
    job_id: str | None = None
    items: list[MarketDataBatchItemResult] = Field(default_factory=list)
    message: str | None = None


class MarketDataSummaryResponse(BaseModel):
    total_datasets: int
    available_symbols: list[str]
    available_timeframes: list[str]
    pass_count: int
    warning_count: int
    fail_count: int
    latest_updated_at: str | None = None
    by_symbol: dict[str, dict[str, Any]] = Field(default_factory=dict)


class MarketDataPreviewResponse(BaseModel):
    dataset_id: str
    timeframe: str
    total_rows: int
    rows: list[dict[str, Any]]


class Top10UniverseRefreshRequest(BaseModel):
    market_scope: Literal["KRW", "BTC", "USDT"] = "KRW"
    top_n: int = Field(default=10, ge=1, le=200)
    use_job: bool = False


class Top10UniverseCollectRequest(BaseModel):
    include_seconds: bool = False
    validate_after_collect: bool = True
    overwrite_existing: bool = False
    use_job: bool = False
    start_date: date | None = None
    end_date: date | None = None


class Top10UniverseUpdateRequest(BaseModel):
    include_seconds: bool = False
    validate_after_collect: bool = True
    use_job: bool = False
    end_date: date | None = None


class Top10UniverseResponse(BaseModel):
    universe_id: str
    generated_at: str
    updated_at: str
    source_exchange: str
    market_scope: str
    ranking_source: str
    selected_count: int
    selected_markets: list[str]
    selected_symbols: list[str]
    selected_rows: list[dict[str, Any]]
    market_cap_snapshot: dict[str, Any] = Field(default_factory=dict)
    collection_policy: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = None


class Top10UniverseSummaryResponse(BaseModel):
    universe_id: str | None = None
    generated_at: str | None = None
    market_scope: str | None = None
    selected_markets: list[str] = Field(default_factory=list)
    selected_symbols: list[str] = Field(default_factory=list)
    included_timeframes: list[str] = Field(default_factory=list)
    include_seconds: bool = False
    total_combinations: int = 0
    pass_count: int = 0
    warning_count: int = 0
    fail_count: int = 0
    missing_dataset_count: int = 0
    failed_dataset_count: int = 0
    latest_updated_at: str | None = None
    total_row_count: int = 0
    coverage_by_symbol: dict[str, Any] = Field(default_factory=dict)


class Top10UniverseMissingItem(BaseModel):
    symbol: str
    timeframe: str


class Top10UniverseMissingResponse(BaseModel):
    universe_id: str | None = None
    include_seconds: bool = False
    total_missing: int = 0
    items: list[Top10UniverseMissingItem] = Field(default_factory=list)


class Top10UniverseRetryMissingRequest(BaseModel):
    include_seconds: bool = False
    validate_after_collect: bool = True
    overwrite_existing: bool = False
    use_job: bool = False
    start_date: date | None = None
    end_date: date | None = None


class Top10UniverseActionResponse(BaseModel):
    mode: Literal["sync", "job"]
    job_id: str | None = None
    message: str | None = None
    result: dict[str, Any] | None = None


MarketDataJobStatus = Literal["queued", "running", "completed", "failed", "cancelled"]


class MarketDataJobResponse(BaseModel):
    job_id: str
    job_type: str
    status: MarketDataJobStatus
    progress: float
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_seconds: float | None = None
    related_dataset_id: str | None = None
    error_summary: str | None = None
    error_detail: str | None = None
    retry_count: int = 0
    parent_job_id: str | None = None
    request_hash: str
    duplicate_of_job_id: str | None = None
    batch_id: str | None = None
    total_combinations: int | None = None
    completed_combinations: int | None = None
    failed_combinations: int | None = None
    current_symbol: str | None = None
    current_timeframe: str | None = None
    combination_results: list[dict[str, Any]] | None = None
    request: dict[str, Any]


class MarketDataJobListResponse(BaseModel):
    items: list[MarketDataJobResponse]
