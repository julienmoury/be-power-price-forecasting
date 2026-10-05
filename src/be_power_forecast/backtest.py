"""Rolling-window backtest: recalibrate every day, forecast the next day's 24 prices."""

from __future__ import annotations

import os
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

from be_power_forecast.models.lear import DEFAULT_SPEC, LEAR, FeatureSpec, build_features

HOURS = [f"h{h}" for h in range(24)]


def daily_prices(
    df: pd.DataFrame, begin: str | None = None, end: str | None = None
) -> pd.DataFrame:
    """Prices of a standard frame as a ``(n_days, 24)`` frame indexed by day."""
    price = df["Price"].to_numpy().reshape(-1, 24)
    out = pd.DataFrame(price, index=pd.DatetimeIndex(df.index[::24]), columns=HOURS)
    return out.loc[begin:end]


def _forecast_days(args) -> np.ndarray:
    X, Y, days, calibration_window, spec, alpha_selection = args
    model = LEAR(calibration_window, alpha_selection)
    # One BLAS thread per worker: the parallelism is across forecast days.
    with threadpool_limits(limits=1):
        return np.array([model.forecast_day(X, Y, t, spec) for t in days])


def lear_backtest(
    df: pd.DataFrame,
    begin: str,
    end: str,
    calibration_window: int,
    spec: FeatureSpec = DEFAULT_SPEC,
    alpha_selection: str = "legacy",
    n_jobs: int | None = None,
) -> pd.DataFrame:
    """Daily-recalibrated LEAR forecasts for every day in ``[begin, end]``.

    Only data strictly before each forecast day enters its calibration (exogenous
    forecasts of the target day are inputs, as they are published before gate closure).
    """
    X, Y, dates = build_features(df, spec)
    target = np.flatnonzero((dates >= pd.Timestamp(begin)) & (dates <= pd.Timestamp(end)))
    n_jobs = n_jobs or os.cpu_count() or 1
    chunks = [c for c in np.array_split(target, n_jobs * 4) if len(c)]
    jobs = [(X, Y, c, calibration_window, spec, alpha_selection) for c in chunks]
    if n_jobs == 1:
        parts = [_forecast_days(j) for j in jobs]
    else:
        with ProcessPoolExecutor(n_jobs) as pool:
            parts = list(pool.map(_forecast_days, jobs))
    return pd.DataFrame(np.vstack(parts), index=dates[target], columns=HOURS)
