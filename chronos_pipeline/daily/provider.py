from abc import ABC, abstractmethod
from datetime import date

import pandas as pd


class DailyBarProvider(ABC):
    provider_name = 'unknown'

    @abstractmethod
    def fetch_daily_bars(self, code: str, start_date: date, end_date: date) -> pd.DataFrame:
        pass
