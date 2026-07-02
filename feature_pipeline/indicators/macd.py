from __future__ import annotations

import numpy as np
import talib


def compute_macd(
    close: np.ndarray,
    *,
    fastperiod: int = 12,
    slowperiod: int = 26,
    signalperiod: int = 9,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    values = np.asarray(close, dtype=np.float64)
    return talib.MACD(
        values,
        fastperiod=fastperiod,
        slowperiod=slowperiod,
        signalperiod=signalperiod,
    )
