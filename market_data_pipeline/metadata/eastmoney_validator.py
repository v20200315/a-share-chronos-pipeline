from __future__ import annotations

import pandas as pd

from .validator import MetadataValidator, ValidationReport


class EastMoneyMetadataValidator(MetadataValidator):
    provider_name = 'eastmoney'

    @classmethod
    def validate_stock_basic(
        cls,
        df: pd.DataFrame,
        *,
        previous_df: pd.DataFrame | None = None,
        strict: bool = False,
    ) -> ValidationReport:
        return super().validate_stock_basic(
            df,
            previous_df=previous_df,
            strict=strict,
        )
