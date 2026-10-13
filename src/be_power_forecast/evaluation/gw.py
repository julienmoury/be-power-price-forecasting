# Adapted from jeslago/epftoolbox (epftoolbox/evaluation/_gw.py) by Jesus Lago (Apache-2.0)
# — changes: plotting removed; returns the statistic as well as the p-value; the (T, T)
# broadcast of the regression residuals is replaced by the equivalent (T,) vector; adds a
# pairwise matrix helper.
"""Giacomini-White test of conditional predictive ability (Giacomini & White, 2006).

The test used for the results of Lago et al. (2021, §5.5.2 and §6.2). The loss
differential Delta_d is regressed on the information set of day d-1, a constant and
Delta_{d-1} (the Diebold-Mariano test is the case with the constant only). As in DM, the
multivariate version works on daily-averaged loss differentials.

The test is one-sided: H0 says forecast 1 is at least as accurate as forecast 2. A small
p-value means forecast 2 is significantly more accurate than forecast 1.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


def _statistic(d: np.ndarray, tau: int = 1) -> tuple[float, int]:
    """T * R^2 of the regression of 1 on (1, Delta_{d-1}) * Delta_d, and its d.o.f."""
    instruments = np.stack([np.ones_like(d[:-tau]), d[:-tau]])
    reg = instruments * d[tau:]
    t = d.shape[0] - tau
    betas = np.linalg.lstsq(reg.T, np.ones(t), rcond=None)[0]
    err = 1 - reg.T @ betas
    return t * (1 - np.mean(err**2)), reg.shape[0]


def gw_test(p_real, p_pred_1, p_pred_2, norm: int = 1, version: str = "multivariate"):
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
    d = loss(p_real - p_pred_1) - loss(p_real - p_pred_2)
    tau = 1  # one-step (day-ahead) forecasts only, as in the original
    if version == "univariate":
        stat, q = np.array([_statistic(d[:, h], tau)[0] for h in range(d.shape[1])]), 2
        # The original signs with the mean over all days (not the d[tau:] used in the fit).
        stat = stat * np.sign(np.mean(d, axis=0))
    elif version == "multivariate":
        d = d.mean(axis=1)
        stat, q = _statistic(d, tau)
        stat = stat * np.sign(np.mean(d[tau:]))
    else:
        raise ValueError("version must be 'univariate' or 'multivariate'")
    return stat, 1 - stats.chi2.cdf(stat, q)


def gw_matrix(p_real: np.ndarray, forecasts: dict[str, np.ndarray], norm: int = 1) -> pd.DataFrame:
    """Pairwise multivariate GW p-values; cell (row, col) tests 'col better than row'."""
    names = list(forecasts)
    out = pd.DataFrame(np.nan, index=names, columns=names)
    for a in names:
        for b in names:
            if a != b:
                out.loc[a, b] = gw_test(p_real, forecasts[a], forecasts[b], norm=norm)[1]
    return out
