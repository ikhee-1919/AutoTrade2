from abc import ABC, abstractmethod
from datetime import date

from app.models.candle import Candle


class BaseDataProvider(ABC):
    @abstractmethod
    def load_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        start_date: date,
        end_date: date,
    ) -> list[Candle]:
        raise NotImplementedError
