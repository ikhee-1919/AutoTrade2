from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.models.candle import Candle


@dataclass(frozen=True)
class StrategyMetadata:
    strategy_id: str
    name: str
    version: str
    description: str
    mode: str = "single_timeframe"
    required_roles: list[str] | None = None
    optional_roles: list[str] | None = None


@dataclass(frozen=True)
class StrategyDecision:
    strategy_name: str
    regime: str
    entry_allowed: bool
    score: float
    reject_reason: str | None
    stop_loss: float | None
    take_profit: float | None
    debug_info: dict[str, Any]
    strategy_version: str | None = None
    reason_tags: list[str] | None = None


@dataclass(frozen=True)
class StrategyContext:
    symbol: str
    timeframe_mapping: dict[str, str]
    candles_by_role: dict[str, list[Candle]]
    metadata_by_role: dict[str, dict[str, Any]]
    as_of: datetime
    entry_role: str = "entry"


class BaseStrategy(ABC):
    @abstractmethod
    def metadata(self) -> StrategyMetadata:
        raise NotImplementedError

    @abstractmethod
    def default_params(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def validate_params(self, params: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def uses_context(self) -> bool:
        return False

    def required_timeframe_roles(self) -> list[str]:
        return []

    def optional_timeframe_roles(self) -> list[str]:
        return []

    def default_timeframe_mapping(self) -> dict[str, str]:
        return {}

    def warmup_candles(self, params: dict[str, Any]) -> int:
        candidates = []
        for key in ("long_window", "volume_window", "short_window"):
            value = params.get(key)
            if isinstance(value, int):
                candidates.append(value)
        return max(candidates) if candidates else 30

    @abstractmethod
    def evaluate(self, candles: list[Candle], params: dict[str, Any]) -> StrategyDecision:
        raise NotImplementedError

    def evaluate_context(self, context: StrategyContext, params: dict[str, Any]) -> StrategyDecision:
        entry_candles = context.candles_by_role.get(context.entry_role, [])
        if not entry_candles:
            return StrategyDecision(
                strategy_name=self.metadata().name,
                regime="unknown",
                entry_allowed=False,
                score=0.0,
                reject_reason="missing_entry_candles",
                stop_loss=None,
                take_profit=None,
                debug_info={"available_roles": list(context.candles_by_role.keys())},
            )
        return self.evaluate(entry_candles, params)
