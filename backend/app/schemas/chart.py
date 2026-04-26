from datetime import date

from pydantic import BaseModel, Field


class ChartDatasetMeta(BaseModel):
    source_type: str
    dataset_id: str | None = None
    symbol: str
    timeframe: str
    dataset_signature: str | None = None
    quality_status: str | None = None
    updated_at: str | None = None


class CandleItem(BaseModel):
    time: str
    open: float
    high: float
    low: float
    close: float
    volume: float


class ChartCandlesResponse(BaseModel):
    symbol: str
    timeframe: str
    start_date: date
    end_date: date
    dataset: ChartDatasetMeta | None = None
    items: list[CandleItem]


class IndicatorItem(BaseModel):
    time: str
    ema20: float | None = None
    ema50: float | None = None
    ema120: float | None = None
    rsi14: float | None = None
    volume_ma20: float | None = None


class ChartIndicatorsResponse(BaseModel):
    symbol: str
    timeframe: str
    start_date: date
    end_date: date
    dataset: ChartDatasetMeta | None = None
    indicators: list[str] = Field(default_factory=list)
    items: list[IndicatorItem]


class BacktestOverlayTradeItem(BaseModel):
    entry_time: str
    entry_price: float
    exit_time: str
    exit_price: float
    exit_reason: str
    gross_pct: float
    net_pct: float


class BacktestOverlayMeta(BaseModel):
    strategy_id: str
    strategy_version: str
    code_version: str
    symbol: str
    timeframe: str
    timeframe_mapping: dict[str, str] | None = None


class ChartBacktestOverlayResponse(BaseModel):
    run_id: str
    run_meta: BacktestOverlayMeta
    trades: list[BacktestOverlayTradeItem]
