from __future__ import annotations

import numpy as np
import talib


def compute_rsi(close: np.ndarray, *, timeperiod: int = 14) -> np.ndarray:
    values = np.asarray(close, dtype=np.float64)
    return talib.RSI(values, timeperiod=timeperiod)
