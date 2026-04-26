from typing import Any

from pydantic import BaseModel, Field


class StrategyMetaResponse(BaseModel):
    strategy_id: str
    name: str
    version: str
    description: str
    short_description: str | None = None
    mode: str = "single_timeframe"
    spot_long_only: bool = False
    required_roles: list[str] = Field(default_factory=list)
    optional_roles: list[str] = Field(default_factory=list)


class StrategyDetailResponse(StrategyMetaResponse):
    default_params: dict[str, Any]
    default_timeframe_mapping: dict[str, str] = Field(default_factory=dict)


class StrategyParamsResponse(BaseModel):
    strategy_id: str
    params: dict[str, Any]


class StrategyParamsUpdateRequest(BaseModel):
    params: dict[str, Any] = Field(default_factory=dict)
