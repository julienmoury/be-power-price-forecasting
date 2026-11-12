"""LightGBM challenger, beyond the paper: one gradient-boosted model per delivery hour.

The inputs are those of LEAR (``build_features`` with ``DEFAULT_SPEC``), the target is
asinh-median transformed as in LEAR, and only data before the forecast day enter training.
The configuration was chosen once, on 2015-2016 (``scripts/tune_lgbm.py``), then frozen.
"""

from __future__ import annotations

import multiprocessing as mp
import os
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor

from be_power_forecast.config import SEED
from be_power_forecast.models.lear import DEFAULT_SPEC, WINDOW_BUFFER, FeatureSpec, build_features
from be_power_forecast.models.scaling import InvariantScaler

HOURS = [f"h{h}" for h in range(24)]
FIXED = {"random_state": SEED, "deterministic": True, "force_row_wise": True, "n_jobs": 1}
# Frozen configuration: the lowest MAE of the grid search on 2015-2016 (results/lgbm_tuning.json).
CONFIG = {"calibration_window": 1456, "num_leaves": 15, "learning_rate": 0.03, "n_estimators": 300}


class LGBM:
    """Daily-recalibrated LightGBM model: 24 regressors, one per hour."""

    def __init__(self, calibration_window: int = 1456, **params):
        self.calibration_window = calibration_window
        self.params = {**FIXED, "verbose": -1, **params}

    def recalibrate(self, X: np.ndarray, Y: np.ndarray) -> LGBM:
        self.scaler_y = InvariantScaler()
        Y = self.scaler_y.fit_transform(Y)
        self.models = [LGBMRegressor(**self.params).fit(X, Y[:, h]) for h in range(Y.shape[1])]
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        X = np.atleast_2d(X)
        return self.scaler_y.inverse_transform(np.column_stack([m.predict(X) for m in self.models]))

    def forecast_days(self, X: np.ndarray, Y: np.ndarray, days: np.ndarray, spec: FeatureSpec):
        """Recalibrate on the window ending the day before ``days[0]``, forecast ``days``.

        The window is the one of ``LEAR.forecast_day``: ``calibration_window`` days, the
        first week only serving as lags.
        """
        t = days[0]
        first = t - self.calibration_window + WINDOW_BUFFER
        if first < max(spec.max_lag, WINDOW_BUFFER):
            raise ValueError("not enough history for this calibration window")
        ok = np.isfinite(X[first:t]).all(axis=1) & np.isfinite(Y[first:t]).all(axis=1)
        return self.recalibrate(X[first:t][ok], Y[first:t][ok]).predict(X[days])


def _forecast_blocks(args) -> np.ndarray:
    X, Y, blocks, config, spec = args
    model = LGBM(**config)
    return np.vstack([model.forecast_days(X, Y, b, spec) for b in blocks])


def lgbm_backtest(
    df: pd.DataFrame,
    begin: str,
    end: str,
    config: dict = CONFIG,
    retrain_every: int = 1,
    spec: FeatureSpec = DEFAULT_SPEC,
    n_jobs: int | None = None,
) -> pd.DataFrame:
    """LightGBM forecasts for every day in ``[begin, end]``, as ``lear_backtest``.

    With ``retrain_every=k``, the models are retrained every ``k`` calendar days from
    ``begin`` and forecast the days until the next retraining from their own inputs.
    """
    X, Y, dates = build_features(df, spec)
    in_test = (dates >= pd.Timestamp(begin)) & (dates <= pd.Timestamp(end))
    target = np.flatnonzero(in_test & np.isfinite(X).all(axis=1) & np.isfinite(Y).all(axis=1))
    block = (dates[target] - pd.Timestamp(begin)).days // retrain_every
    blocks = [target[block == b] for b in np.unique(block)]
    n_jobs = n_jobs or os.cpu_count() or 1
    chunks = [c for c in np.array_split(np.arange(len(blocks)), n_jobs * 4) if len(c)]
    jobs = [(X, Y, [blocks[i] for i in c], config, spec) for c in chunks]
    if n_jobs == 1:
        parts = [_forecast_blocks(j) for j in jobs]
    else:
        # "spawn": a process forked after LightGBM started its OpenMP threads can deadlock.
        with ProcessPoolExecutor(n_jobs, mp_context=mp.get_context("spawn")) as pool:
            parts = list(pool.map(_forecast_blocks, jobs))
    return pd.DataFrame(np.vstack(parts), index=dates[target], columns=HOURS)
