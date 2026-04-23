from app.strategy.registry import StrategyRegistry


class StrategyCatalogRepository:
    def __init__(self, registry: StrategyRegistry) -> None:
        self._registry = registry

    def list_strategy_ids(self) -> list[str]:
        return [strategy.metadata().strategy_id for strategy in self._registry.list()]
