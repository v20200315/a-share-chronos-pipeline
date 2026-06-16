from dataclasses import dataclass


@dataclass(slots=True)
class StockBasic:
    code: str
    name: str
    exchange: str

    list_date: str | None = None


@dataclass(slots=True)
class DailyBar:
    code: str
    date: str
    open: float | None
    high: float | None
    low: float | None
    close: float | None
    volume: float | None
    amount: float | None
    amplitude: float | None
    pct_change: float | None
    change: float | None
    turnover: float | None
