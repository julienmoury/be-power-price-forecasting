# Adapted from jeslago/epftoolbox (epftoolbox/data/_wrangling.py) by Jesus Lago (Apache-2.0)
# — changes: kept only the median/MAD and asinh ("Invariant") scalers, vectorised the
# column loops, raise on misuse instead of printing, guard against zero MAD.
"""Variance-stabilising asinh-median scaling (Uniejewski, Weron & Ziel, 2018)."""

from __future__ import annotations

import numpy as np
from statsmodels.robust import mad


class InvariantScaler:
    """``asinh((x - median) / MAD)`` column-wise, with its exact inverse."""

    def fit(self, data: np.ndarray) -> InvariantScaler:
        data = _as_2d(data)
        self.median_ = np.median(data, axis=0)
        scale = mad(data, axis=0)
        # A constant column would divide by zero; leave it centred but unscaled.
        self.mad_ = np.where(scale > 0, scale, 1.0)
        return self

    def transform(self, data: np.ndarray) -> np.ndarray:
        return np.arcsinh((_as_2d(data) - self.median_) / self.mad_)

    def fit_transform(self, data: np.ndarray) -> np.ndarray:
        return self.fit(data).transform(data)

    def inverse_transform(self, data: np.ndarray) -> np.ndarray:
        return np.sinh(_as_2d(data)) * self.mad_ + self.median_


def _as_2d(data: np.ndarray) -> np.ndarray:
    data = np.asarray(data, dtype=float)
    if data.ndim != 2:
        raise ValueError("expected a 2-D array of shape (n_samples, n_features)")
    return data
