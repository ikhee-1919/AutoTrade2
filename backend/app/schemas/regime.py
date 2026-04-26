from datetime import date

from pydantic import BaseModel, Field


class RegimeDailyPoint(BaseModel):
    date: date
    close: float
    sma200: float | None = None
    ema20: float | None = None
    ema50: float | None = None
    ema200: float | None = None
    sma200_slope_5d: float | None = None
    sma200_slope_20d: float | None = None
    distance_from_sma200_pct: float | None = None
    above_sma200: bool | None = None
    has_sufficient_history: bool
    regime: str


class RegimeSegment(BaseModel):
    label: str
    start_date: date
    end_date: date
    days: int
    start_close: float
    end_close: float
    return_pct: float
    avg_distance_from_sma200_pct: float
    sma200_slope_state: str


class RegimeAnalyzeResponse(BaseModel):
    symbol: str
    indicator_start: date
    analysis_start: date
    analysis_end: date
    dataset: dict[str, str | None] = Field(default_factory=dict)
    regime_counts: dict[str, int] = Field(default_factory=dict)
    above_200_days: int = 0
    below_200_days: int = 0
    insufficient_history_days: int = 0
    above_200_return: float = 0.0
    below_200_return: float = 0.0
    daily_points: list[RegimeDailyPoint] = Field(default_factory=list)
    regime_segments: list[RegimeSegment] = Field(default_factory=list)
    above_200_segments: list[RegimeSegment] = Field(default_factory=list)
    below_200_segments: list[RegimeSegment] = Field(default_factory=list)


class RegimeBatchAnalyzeResponse(BaseModel):
    indicator_start: date
    analysis_start: date
    analysis_end: date
    items: list[RegimeAnalyzeResponse] = Field(default_factory=list)
    summary: dict[str, int | float] = Field(default_factory=dict)
