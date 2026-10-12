"""Drift rule: alert when the rolling 30-day error of the deployed forecast is unusually high.

The threshold is the 95th percentile of the rolling 30-day MAE over the phase A test
(2015-2016), then applied out of sample to the phase B test (2019-2026). The same rule on
the rolling 30-day rMAE (MAE of the forecast / MAE of the naive forecast over the same
days) is a scale-free robustness check: it does not alert just because prices are higher.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

WINDOW = 30
QUANTILE = 0.95


def daily_abs_error(real: pd.DataFrame, pred: pd.DataFrame) -> pd.Series:
    """Mean absolute error of each day of two ``(n_days, 24)`` frames, indexed by day."""
    return (real - pred).abs().mean(axis=1)


def _full_windows(rolled: pd.Series, first_day: pd.Timestamp, window: int) -> pd.Series:
    # A value exists once a full window of calendar days has elapsed since the first day.
    return rolled[rolled.index >= first_day + pd.Timedelta(days=window - 1)]


def rolling_mae(daily: pd.Series, window: int = WINDOW) -> pd.Series:
    """Mean of the daily errors over the last ``window`` calendar days.

    Days absent from the index (not forecast) are skipped: the mean is over the days of the
    window that have an error.
    """
    return _full_windows(daily.rolling(f"{window}D").mean(), daily.index[0], window)


def rolling_rmae(daily: pd.Series, daily_ref: pd.Series, window: int = WINDOW) -> pd.Series:
    """Rolling MAE of a forecast divided by the rolling MAE of a reference on the same days."""
    num = daily.rolling(f"{window}D").sum()
    den = daily_ref.reindex(daily.index).rolling(f"{window}D").sum()
    return _full_windows(num / den, daily.index[0], window)


def threshold(rolling: pd.Series, q: float = QUANTILE) -> float:
    """Alert threshold: the ``q`` quantile of a rolling error series (linear interpolation)."""
    return float(np.quantile(rolling.dropna().to_numpy(), q))


def alert_episodes(rolling: pd.Series, thr: float) -> list[dict]:
    """Runs of consecutive values above ``thr``: first day, last day and number of days.

    Consecutive means adjacent in the series, so days that were not forecast do not end an
    episode.
    """
    above = (rolling > thr).to_numpy()
    starts = np.flatnonzero(above & ~np.r_[False, above[:-1]])
    ends = np.flatnonzero(above & ~np.r_[above[1:], False])
    idx = rolling.index
    return [
        {"start": str(idx[s].date()), "end": str(idx[e].date()), "days": int(e - s + 1)}
        for s, e in zip(starts, ends, strict=True)
    ]


def first_monthly_exceedance(
    daily: pd.Series, base: tuple[str, str], start: str, factor: float = 2.0
) -> dict | None:
    """First month from ``start`` whose MAE exceeds ``factor`` times the base-period average.

    The monthly MAE is the mean of the daily errors of the month; the base average is the
    mean of the monthly MAEs of ``base``. The exceedance is only known once the month is
    over, so ``known_on`` is the month's last day.
    """
    monthly = daily.resample("MS").mean()
    base_avg = float(monthly.loc[base[0] : base[1]].mean())
    over = monthly.loc[start:][monthly.loc[start:] > factor * base_avg]
    if over.empty:
        return None
    month = over.index[0]
    return {
        "month": str(month.date())[:7],
        "known_on": str((month + pd.offsets.MonthEnd(0)).date()),
        "monthly_MAE": float(over.iloc[0]),
        "base_monthly_MAE": base_avg,
    }
