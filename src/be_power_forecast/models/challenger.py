"""LightGBM challenger: one gradient-boosted model per delivery hour on the LEAR inputs.

Same design matrix as LEAR (``build_features``), same target days, same rule: only data
before the forecast day enter training (exogenous forecasts of the day are inputs). The
target is asinh-median transformed as in LEAR. Models are retrained every ``retrain_every``
days on the ``calibration_window`` days before the retraining day; in between, the last
models forecast each day from that day's inputs.
"""

from __future__ import annotations

import itertools
import multiprocessing
import os
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor

from be_power_forecast.config import SEED
from be_power_forecast.models.lear import DEFAULT_SPEC, WINDOW_BUFFER, FeatureSpec, build_features
from be_power_forecast.models.scaling import InvariantScaler

GRID = {
    "num_leaves": (15, 31),
    "learning_rate": (0.03, 0.1),
    "n_estimators": (300, 600),
}
FIXED = {
    "min_child_samples": 20,
    "random_state": SEED,
    "deterministic": True,
    "force_row_wise": True,
    "n_jobs": 1,
    "verbose": -1,
}
HOURS = [f"h{h}" for h in range(24)]
_DATA: dict = {}  # design matrix shared with worker processes (set once per process)


def _init(X: np.ndarray, Y: np.ndarray) -> None:
    _DATA["X"], _DATA["Y"] = X, Y


def _fit_forecast(args) -> np.ndarray:
    """Train 24 models on the window before ``days[0]`` and forecast every day of ``days``."""
    days, calibration_window, params = args
    X, Y = _DATA["X"], _DATA["Y"]
    t0 = days[0]
    first = t0 - calibration_window + WINDOW_BUFFER
    if first < WINDOW_BUFFER:
        raise ValueError("not enough history for this calibration window")
    Xw, Yw = X[first:t0], Y[first:t0]
    ok = np.isfinite(Xw).all(axis=1) & np.isfinite(Yw).all(axis=1)
    scaler = InvariantScaler()
    Yw = scaler.fit_transform(Yw[ok])
    preds = np.column_stack(
        [LGBMRegressor(**FIXED, **params).fit(Xw[ok], Yw[:, h]).predict(X[days]) for h in range(24)]
    )
    return scaler.inverse_transform(preds)


def lgbm_backtest(
    df: pd.DataFrame,
    begin: str,
    end: str,
    params: dict,
    calibration_window: int = 1456,
    retrain_every: int = 7,
    spec: FeatureSpec = DEFAULT_SPEC,
    n_jobs: int | None = None,
) -> pd.DataFrame:
    """LightGBM forecasts for every day in ``[begin, end]`` (days dropped by the data rules
    are skipped), retrained every ``retrain_every`` calendar days from ``begin``."""
    X, Y, dates = build_features(df, spec)
    in_test = (dates >= pd.Timestamp(begin)) & (dates <= pd.Timestamp(end))
    target = np.flatnonzero(in_test & np.isfinite(X).all(axis=1) & np.isfinite(Y).all(axis=1))
    block = (dates[target] - pd.Timestamp(begin)).days // retrain_every
    blocks = np.unique(block)
    groups = [target[block == b] for b in blocks]
    # Each block is trained on the window before the block's first calendar day.
    first_days = pd.Timestamp(begin) + pd.to_timedelta(blocks * retrain_every, unit="D")
    starts = np.searchsorted(dates, first_days)
    jobs = [
        (np.concatenate([[s], g]), calibration_window, params)
        for s, g in zip(starts, groups, strict=True)
    ]
    n_jobs = n_jobs or os.cpu_count() or 1
    if n_jobs == 1:
        _init(X, Y)
        parts = [_fit_forecast(j)[1:] for j in jobs]
    else:
        # "spawn": forking a process in which LightGBM's OpenMP threads started can deadlock.
        ctx = multiprocessing.get_context("spawn")
        with ProcessPoolExecutor(n_jobs, ctx, initializer=_init, initargs=(X, Y)) as pool:
            parts = [p[1:] for p in pool.map(_fit_forecast, jobs)]
    return pd.DataFrame(np.vstack(parts), index=dates[target], columns=HOURS)


def tune(
    df: pd.DataFrame,
    begin: str,
    end: str,
    calibration_window: int,
    n_jobs: int | None = None,
) -> tuple[dict, list[dict]]:
    """Grid search by walk-forward MAE on ``[begin, end]`` (weekly retraining).

    Returns the best parameters and the MAE of every grid point.
    """
    real = None
    scores = []
    for values in itertools.product(*GRID.values()):
        params = dict(zip(GRID, values, strict=True))
        fc = lgbm_backtest(df, begin, end, params, calibration_window, n_jobs=n_jobs)
        if real is None:
            price = df["Price"].to_numpy().reshape(-1, 24)
            days = pd.DatetimeIndex(df.index[::24])
            real = price[days.get_indexer(fc.index)]
        scores.append({**params, "MAE": float(np.mean(np.abs(fc.to_numpy() - real)))})
    best = min(scores, key=lambda s: s["MAE"])
    return {k: best[k] for k in GRID}, scores
