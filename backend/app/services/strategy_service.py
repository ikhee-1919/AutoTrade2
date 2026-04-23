from app.repositories.strategy_params_repository import StrategyParamsRepository
from app.strategy.base import BaseStrategy
from app.strategy.registry import StrategyRegistry


class StrategyService:
    def __init__(self, registry: StrategyRegistry, params_repo: StrategyParamsRepository) -> None:
        self._registry = registry
        self._params_repo = params_repo

    def list_strategies(self) -> list[BaseStrategy]:
        return self._registry.list()

    def get_strategy(self, strategy_id: str) -> BaseStrategy:
        return self._registry.get(strategy_id)

    def get_effective_params(self, strategy_id: str) -> dict:
        strategy = self.get_strategy(strategy_id)
        saved = self._params_repo.get(strategy_id)
        if saved is None:
            return strategy.default_params()
        return strategy.validate_params(saved)

    def update_params(self, strategy_id: str, params: dict) -> dict:
        strategy = self.get_strategy(strategy_id)
        current = self.get_effective_params(strategy_id)
        merged = current | params
        validated = strategy.validate_params(merged)
        self._params_repo.save(strategy_id, validated)
        return validated
