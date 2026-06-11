from abc import ABC, abstractmethod

import pandas as pd

from .validator import CrossCheckRefs


class MetadataProvider(ABC):
    provider_name = 'unknown'

    @property
    def last_cross_check(self) -> CrossCheckRefs | None:
        return None

    @abstractmethod
    def fetch_stock_basic(self) -> pd.DataFrame:
        pass
