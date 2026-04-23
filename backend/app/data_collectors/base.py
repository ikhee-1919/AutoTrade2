from abc import ABC, abstractmethod
from datetime import date
from typing import Callable

from app.models.candle import Candle


class HistoricalCandleCollector(ABC):
    @abstractmethod
    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        start_date: date,
        end_date: date,
        progress_callback: Callable[[float], None] | None = None,
    ) -> list[Candle]:
        raise NotImplementedError
