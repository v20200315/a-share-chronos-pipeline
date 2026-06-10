from abc import ABC, abstractmethod

import pandas as pd


class MetadataProvider(ABC):
    @abstractmethod
    def fetch_stock_basic(self) -> pd.DataFrame:
        pass
