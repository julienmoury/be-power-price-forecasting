"""Additive attribution of the MAE gap between two forecasts to segments of hours.

The analogue of a Brinson attribution of relative portfolio performance: for a candidate A
and a reference B evaluated on the same hours, partitioned into segments s,

    MAE_A - MAE_B = sum_s w_s * (MAE_A,s - MAE_B,s),   w_s = hours in s / total hours,

so each segment contributes ``c_s = w_s * (MAE_A,s - MAE_B,s)`` and the contributions add
up exactly to the gap.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

SEASONS = {12: "DJF", 1: "DJF", 2: "DJF", 3: "MAM", 4: "MAM", 5: "MAM",
           6: "JJA", 7: "JJA", 8: "JJA", 9: "SON", 10: "SON", 11: "SON"}  # fmt: skip


def mae_gap_attribution(real, pred_a, pred_b, segments) -> pd.DataFrame:
    """Contribution of each segment to ``MAE(pred_a) - MAE(pred_b)``.

    ``real``, ``pred_a``, ``pred_b`` and ``segments`` have the same shape (e.g.
    ``(n_days, 24)``); ``segments`` holds the segment label of every hour. Returns one row
    per segment (hours, weight, MAE of A and B, gap, contribution, share of the total gap)
    and a ``total`` row.
    """
    real, a, b = (np.asarray(x, dtype=float).ravel() for x in (real, pred_a, pred_b))
    labels = np.asarray(segments).ravel()
    errors = pd.DataFrame({"segment": labels, "A": np.abs(a - real), "B": np.abs(b - real)})
    g = errors.groupby("segment", sort=True)
    out = pd.DataFrame({"hours": g.size(), "MAE_A": g["A"].mean(), "MAE_B": g["B"].mean()})
    out["weight"] = out["hours"] / len(errors)
    out["gap"] = out["MAE_A"] - out["MAE_B"]
    out["contribution"] = out["weight"] * out["gap"]
    total_gap = errors["A"].mean() - errors["B"].mean()
    out["share"] = out["contribution"] / total_gap if total_gap else np.nan
    out.loc["total"] = [len(errors), errors["A"].mean(), errors["B"].mean(), 1.0,
                        total_gap, out["contribution"].sum(), out["share"].sum()]  # fmt: skip
    return out


def hour_segments(days: pd.DatetimeIndex) -> np.ndarray:
    """Delivery hour (0-23) of every hour of ``days``."""
    return np.tile(np.arange(24), (len(days), 1))


def season_segments(days: pd.DatetimeIndex) -> np.ndarray:
    """Meteorological season (DJF, MAM, JJA, SON) of every hour of ``days``."""
    seasons = np.array([SEASONS[m] for m in days.month])
    return np.repeat(seasons[:, None], 24, axis=1)


def spike_thresholds(
    days: pd.DatetimeIndex, history: pd.Series, window: int = 1456, quantile: float = 0.95
) -> pd.Series:
    """Per forecast day, the ``quantile`` of the hourly prices of the ``window`` days before
    it (history only, no look-ahead)."""
    hist = history.dropna()
    one_hour = pd.Timedelta(hours=1)
    return pd.Series(
        [
            np.quantile(hist.loc[d - pd.Timedelta(days=window) : d - one_hour], quantile)
            for d in days
        ],
        index=days,
    )


def regime_segments(real: pd.DataFrame, history: pd.Series, window: int = 1456) -> np.ndarray:
    """Price regime of every hour: ``negative`` (price < 0), ``spike`` (price above the
    95th percentile of the hourly prices of the ``window`` days before the forecast day) or
    ``normal``. ``real`` is the ``(n_days, 24)`` frame of realised prices indexed by day;
    ``history`` the hourly price series of the standard frame, covering the window.
    """
    threshold = spike_thresholds(pd.DatetimeIndex(real.index), history, window).to_numpy()
    values = real.to_numpy()
    labels = np.full(values.shape, "normal", dtype=object)
    labels[values > threshold[:, None]] = "spike"
    labels[values < 0] = "negative"
    return labels
