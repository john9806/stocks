from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class DailyPrice:
    ticker: str
    trade_date: date
    open_price: float
    close_price: float
    high_price: float | None = None
    low_price: float | None = None
    volume: int | None = None


@dataclass(frozen=True)
class DividendEvent:
    ticker: str
    ex_date: date
    dividend_amount: float
