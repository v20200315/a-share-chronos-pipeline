from abc import ABC, abstractmethod

import pandas as pd


class MetadataProvider(ABC):
    provider_name = 'unknown'

    @abstractmethod
    def fetch_stock_basic(self) -> pd.DataFrame:
        pass
