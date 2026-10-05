# Adapted from jeslago/epftoolbox (epftoolbox/evaluation/_dm.py) by Jesus Lago (Apache-2.0)
# — changes: plotting removed (see be_power_forecast.report); returns the statistic as well
# as the p-value; adds a pairwise matrix helper.
"""Diebold-Mariano test for day-ahead forecasts (Diebold & Mariano, 1995).

The loss differential is computed per day, so that the 24 hourly errors of a day (which
are forecast with the same information set) do not violate the test's assumptions
(Ziel & Weron, 2018; Lago et al., 2021).

The test is one-sided: H0 says forecast 1 is at least as accurate as forecast 2. A small
p-value means forecast 2 is significantly more accurate than forecast 1.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


def dm_test(p_real, p_pred_1, p_pred_2, norm: int = 1, version: str = "multivariate"):
    """Return ``(statistic, p_value)``; arrays have shape ``(n_days, 24)``.

    ``version="univariate"`` returns one test per hour (arrays of length 24).
    """
    p_real, p_pred_1, p_pred_2 = (np.asarray(a, dtype=float) for a in (p_real, p_pred_1, p_pred_2))
    if not p_real.shape == p_pred_1.shape == p_pred_2.shape:
        raise ValueError("the three arrays must have the same shape")
    if p_real.ndim != 2 or p_real.shape[1] == 1:
        raise ValueError("arrays must have shape (n_days, n_prices_per_day)")
    if norm not in (1, 2):
        raise ValueError("norm must be 1 or 2")

    loss = np.abs if norm == 1 else np.square
    l1, l2 = loss(p_real - p_pred_1), loss(p_real - p_pred_2)
    if version == "univariate":
        d = l1 - l2
        axis = 0
    elif version == "multivariate":
        d = l1.mean(axis=1) - l2.mean(axis=1)
        axis = None
    else:
        raise ValueError("version must be 'univariate' or 'multivariate'")
    n = d.shape[0]
    stat = np.mean(d, axis=axis) / np.sqrt(np.var(d, ddof=0, axis=axis) / n)
    return stat, 1 - stats.norm.cdf(stat)


def dm_matrix(p_real: np.ndarray, forecasts: dict[str, np.ndarray], norm: int = 1) -> pd.DataFrame:
    """Pairwise multivariate DM p-values; cell (row, col) tests 'col better than row'."""
    names = list(forecasts)
    out = pd.DataFrame(np.nan, index=names, columns=names)
    for a in names:
        for b in names:
            if a != b:
                out.loc[a, b] = dm_test(p_real, forecasts[a], forecasts[b], norm=norm)[1]
    return out
