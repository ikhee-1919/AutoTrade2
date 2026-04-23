from dataclasses import dataclass
from datetime import datetime


@dataclass
class Position:
    entry_time: datetime
    intended_entry_price: float
    entry_price: float
    stop_loss: float
    take_profit: float
    reason: str
