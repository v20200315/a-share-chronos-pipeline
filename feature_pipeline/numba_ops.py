from __future__ import annotations

import numpy as np
from numba import njit


@njit(cache=True)
def finite_pair_mask(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    mask = np.empty(left.shape[0], dtype=np.bool_)
    for idx in range(left.shape[0]):
        mask[idx] = np.isfinite(left[idx]) and np.isfinite(right[idx])
    return mask
