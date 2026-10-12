"""Hour-by-hour comparison of two sources of the same series on their common hours.

Used to check whether the ENTSO-E series reproduce the benchmark dataset of Lago et al.
(2021) where both exist (2015-2016), before any decision to join them.
"""

from __future__ import annotations

import pandas as pd

from be_power_forecast.data.calendar import HOURS, to_local_days


def local_hourly(series: pd.Series) -> tuple[pd.Series, dict]:
    """Naive local hourly series (24 values per day) from a UTC series, with the day report."""
    days, report = to_local_days(series)
    index = pd.DatetimeIndex([d + pd.Timedelta(hours=h) for d in days.index for h in HOURS])
    return pd.Series(days.to_numpy().ravel(), index=index, name=series.name), report


def compare(reference: pd.Series, other: pd.Series, tol: float = 1e-9) -> dict:
    """Agreement statistics of ``reference - other`` on the hours present in both.

    ``best_shift_hours`` is the shift of ``other`` in {-1, 0, 1} h with the lowest MAE, a
    check of time alignment (a time-zone error shows up as a non-zero best shift).
    """
    both = pd.DataFrame({"ref": reference, "other": other}).dropna()
    diff = both["ref"] - both["other"]
    shifted = {k: (reference - other.shift(k)).abs().mean() for k in (-1, 0, 1)}
    return {
        "hours": len(both),
        "share_equal_pct": float(100 * (diff.abs() <= tol).mean()),
        "mean_reference": float(both["ref"].mean()),
        "bias": float(diff.mean()),
        "mae": float(diff.abs().mean()),
        "mae_pct_of_mean": float(100 * diff.abs().mean() / both["ref"].abs().mean()),
        "max_abs": float(diff.abs().max()),
        "corr": float(both["ref"].corr(both["other"])),
        "best_shift_hours": int(min(shifted, key=shifted.get)),
    }


def monthly(reference: pd.Series, other: pd.Series) -> pd.DataFrame:
    """Monthly mean of each source, bias, MAE and correlation on the common hours."""
    both = pd.DataFrame({"ref": reference, "other": other}).dropna()
    both["diff"] = both["ref"] - both["other"]
    groups = both.groupby(both.index.to_period("M"))
    out = groups.agg(
        reference=("ref", "mean"),
        other=("other", "mean"),
        bias=("diff", "mean"),
        mae=("diff", lambda d: d.abs().mean()),
    )
    out["corr"] = groups.apply(lambda g: g["ref"].corr(g["other"]))
    return out


def largest_daily_gaps(reference: pd.Series, other: pd.Series, n: int = 10) -> pd.Series:
    """The ``n`` days with the largest maximum absolute hourly difference."""
    diff = (reference - other).dropna().abs()
    return diff.groupby(diff.index.normalize()).max().nlargest(n)
