from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class OrderRequest:
    symbol: str
    side: str
    quantity: float
    order_type: str = "market"


@dataclass(frozen=True)
class ExecutionResult:
    accepted: bool
    message: str
    external_order_id: str | None = None


class BaseExecutionAdapter(ABC):
    @abstractmethod
    def submit_order(self, order: OrderRequest) -> ExecutionResult:
        raise NotImplementedError
