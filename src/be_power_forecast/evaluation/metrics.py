# Adapted from the code of Lago et al. (2021), by Jesus Lago (Apache-2.0) — changes: inputs
# restricted to arrays/frames of shape (n_days, 24) indexed by day; naive forecast written
# with vectorised day-of-week shifts; rMAE accepts the naive benchmark explicitly; no
# type-dispatch helpers.
"""Point-forecast error metrics used in the electricity price forecasting literature."""

from __future__ import annotations

import numpy as np
import pandas as pd


def mae(p_real, p_pred) -> float:
    """Mean absolute error, in the unit of the prices (EUR/MWh)."""
    return float(np.mean(np.abs(np.asarray(p_real) - np.asarray(p_pred))))


def rmse(p_real, p_pred) -> float:
    """Root mean squared error."""
    return float(np.sqrt(np.mean((np.asarray(p_real) - np.asarray(p_pred)) ** 2)))


def smape(p_real, p_pred) -> float:
    """Symmetric MAPE, ``mean(2|p - p_hat| / (|p| + |p_hat|))`` (as a fraction, not %)."""
    p_real, p_pred = np.asarray(p_real, float), np.asarray(p_pred, float)
    return float(np.mean(np.abs(p_real - p_pred) / ((np.abs(p_real) + np.abs(p_pred)) / 2)))


def naive_source_day(day: pd.Timestamp) -> pd.Timestamp:
    """Day copied by the standard naive forecast of ``day`` (rule of ``naive_forecast``)."""
    return day - pd.Timedelta(days=7 if day.dayofweek in (0, 5, 6) else 1)


def naive_forecast(prices: pd.DataFrame, m: str | None = None) -> pd.DataFrame:
    """Seasonal naive forecast of a daily ``(n_days, 24)`` price frame.

    ``m=None`` is the standard benchmark of the EPF literature: Monday, Saturday and Sunday
    copy the same day one week before; Tuesday to Friday copy the previous day.
    ``m="D"`` always copies the previous day, ``m="W"`` the same day one week before.
    The first rows without a reference day are dropped.
    """
    idx = pd.DatetimeIndex(prices.index)
    if m == "D":
        lag_days = np.ones(len(idx), dtype=int)
    elif m == "W":
        lag_days = np.full(len(idx), 7)
    elif m is None:
        lag_days = np.where(np.isin(idx.dayofweek, [0, 5, 6]), 7, 1)
    else:
        raise ValueError("m must be None, 'D' or 'W'")
    source = idx - pd.to_timedelta(lag_days, unit="D")
    available = source.isin(idx)
    first_full = 7 if m in (None, "W") else 1
    keep = available & (np.arange(len(idx)) >= first_full)
    values = prices.loc[source[keep]].to_numpy()
    return pd.DataFrame(values, index=idx[keep], columns=prices.columns)


def rmae(p_real: pd.DataFrame, p_pred: pd.DataFrame, m: str | None = None) -> float:
    """Relative MAE: MAE of the forecast divided by the MAE of the naive forecast.

    As in Lago et al. (2021), the naive MAE is computed over the same price series ``p_real``
    (the first week, which has no naive forecast, is excluded from the denominator only).
    """
    naive = naive_forecast(p_real, m=m)
    mae_naive = mae(p_real.loc[naive.index], naive)
    return mae(p_real, p_pred) / mae_naive
