# Adapted from the code of Lago et al. (2021), by Jesus Lago (Apache-2.0)
# — changes: kept the median/MAD and asinh ("Invariant") scalers and the name -> scaler
# mapping of DataScaler, vectorised the column loops, raise on misuse instead of printing,
# guard against zero MAD.
"""Data scalers: asinh-median (Uniejewski, Weron & Ziel, 2018), median/MAD and sklearn's."""

from __future__ import annotations

import numpy as np
from sklearn.preprocessing import MinMaxScaler, StandardScaler
from statsmodels.robust import mad


class MedianScaler:
    """``(x - median) / MAD`` column-wise, with its exact inverse."""

    def fit(self, data: np.ndarray) -> MedianScaler:
        data = _as_2d(data)
        self.median_ = np.median(data, axis=0)
        scale = mad(data, axis=0)
        # A constant column would divide by zero; leave it centred but unscaled.
        self.mad_ = np.where(scale > 0, scale, 1.0)
        return self

    def transform(self, data: np.ndarray) -> np.ndarray:
        return (_as_2d(data) - self.median_) / self.mad_

    def fit_transform(self, data: np.ndarray) -> np.ndarray:
        return self.fit(data).transform(data)

    def inverse_transform(self, data: np.ndarray) -> np.ndarray:
        return _as_2d(data) * self.mad_ + self.median_


class InvariantScaler(MedianScaler):
    """``asinh((x - median) / MAD)`` column-wise, with its exact inverse."""

    def transform(self, data: np.ndarray) -> np.ndarray:
        return np.arcsinh(super().transform(data))

    def inverse_transform(self, data: np.ndarray) -> np.ndarray:
        # sinh in the input precision (float32 network outputs), as in the original.
        return super().inverse_transform(np.sinh(np.asarray(data)))


def make_scaler(name: str):
    """Scaler named as in the original ``DataScaler``; ``None`` for ``"No"`` (no scaling)."""
    scalers = {
        "Norm": lambda: MinMaxScaler(feature_range=(0, 1)),
        "Norm1": lambda: MinMaxScaler(feature_range=(-1, 1)),
        "Std": StandardScaler,
        "Median": MedianScaler,
        "Invariant": InvariantScaler,
    }
    return scalers[name]() if name in scalers else None


def _as_2d(data: np.ndarray) -> np.ndarray:
    data = np.asarray(data, dtype=float)
    if data.ndim != 2:
        raise ValueError("expected a 2-D array of shape (n_samples, n_features)")
    return data
