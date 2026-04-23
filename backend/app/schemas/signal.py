from pydantic import BaseModel


class SymbolListResponse(BaseModel):
    symbols: list[str]


class PricePoint(BaseModel):
    timestamp: str
    close: float


class SignalItem(BaseModel):
    timestamp: str
    price: float
    regime: str
    entry_allowed: bool
    score: float
    reject_reason: str | None


class SignalResponse(BaseModel):
    symbol: str
    strategy_id: str
    timeframe: str
    prices: list[PricePoint]
    signals: list[SignalItem]
