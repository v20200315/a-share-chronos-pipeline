from __future__ import annotations

import pandas as pd

from factor_pipeline.factors.base import pass_through


def compute_technical_factors(df: pd.DataFrame) -> pd.DataFrame:
    """Placeholder technical-factor stage.

    Args:
        df: Cleaned market-data DataFrame.

    Returns:
        The same DataFrame without modification.
    """
    return pass_through(df)
