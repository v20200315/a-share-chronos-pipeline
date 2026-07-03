from __future__ import annotations

import pandas as pd

from factor_pipeline.factors.base import pass_through


def compute_price_factors(df: pd.DataFrame) -> pd.DataFrame:
    """Placeholder price-factor stage.

    Args:
        df: Market-data DataFrame after technical factors.

    Returns:
        The same DataFrame without modification.
    """
    return pass_through(df)
