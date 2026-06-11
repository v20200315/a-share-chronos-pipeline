from dataclasses import dataclass


@dataclass(slots=True)
class StockBasic:
    code: str
    name: str
    exchange: str

    list_date: str | None = None
