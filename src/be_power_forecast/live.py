"""Daily live forecast: update the ENTSO-E series and forecast the next delivery day.

Run every evening by ``scripts/live_forecast.py`` (GitHub Actions, needs ENTSOE_API_KEY),
once the French day-ahead generation forecast of the next day is published (by 18:00, after
the 12:00 gate closure of the day-ahead auction). The model and its inputs are those
of the backtests; only our forecasts are written to the repository, never an ENTSO-E price
(re-use terms; the realised prices shown on the page come from SMARD.de, CC BY 4.0). The raw
ENTSO-E data stay in the cache.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from be_power_forecast.config import EXOGENOUS, PAPER_WINDOWS, TZ
from be_power_forecast.data.calendar import standard_frame, to_local_days
from be_power_forecast.data.entsoe_client import EntsoeClient
from be_power_forecast.data.sources import EntsoeSource, JoinedSource, PriceSource
from be_power_forecast.models.lear import DEFAULT_SPEC, LEAR, build_features, ensemble
from be_power_forecast.models.lgbm import CONFIG, LGBM

OVERLAP_DAYS = 7  # re-downloaded every day: late publications and corrections


def update_raw(source: EntsoeSource, name: str, end: pd.Timestamp) -> pd.Series:
    """UTC series of one column, extended up to local day ``end`` (included) and cached.

    Starts from the cached live series or, the first time, from the download window of
    ``source``; the last ``OVERLAP_DAYS`` days are downloaded again.
    """
    kind, area = source.SERIES[name]
    path = source.cache_dir / f"{kind}_{area}_live.parquet"
    base = pd.read_parquet(path).iloc[:, 0] if path.exists() else source.raw(name)
    start = base.index[-1].tz_convert(TZ).tz_localize(None).normalize()
    start -= pd.Timedelta(days=OVERLAP_DAYS)
    if source.client is None:
        source.client = EntsoeClient()
    try:
        new = source.client.query(kind, area, start, end + pd.Timedelta(days=1))
    except ValueError:  # nothing published yet for that span
        new = base.iloc[:0]
    keep = base[base.index < new.index[0]] if len(new) else base
    series = pd.concat([keep, new]).sort_index()
    series.to_frame().to_parquet(path)
    return series


class _Frame(PriceSource):
    def __init__(self, frame: pd.DataFrame):
        self.frame = frame

    def load(self) -> pd.DataFrame:
        return self.frame


def live_frame(raw: dict[str, pd.Series], day: pd.Timestamp) -> pd.DataFrame:
    """Joined standard frame up to the day before ``day``, plus the inputs known for ``day``.

    The price of ``day`` is unknown (NaN); its French forecasts are filled when published.
    Days between the last complete day and ``day`` are rows of NaN.
    """
    frame = JoinedSource(recent=_Frame(standard_frame(raw)[0])).load()
    hours = pd.date_range(frame.index[0], day + pd.Timedelta(hours=23), freq="h", name="Date")
    frame = frame.loc[: day - pd.Timedelta(hours=1)].reindex(hours)
    for name in EXOGENOUS:
        local = to_local_days(raw[name])[0]
        if day in local.index:
            frame.loc[day : day + pd.Timedelta(hours=23), name] = local.loc[day].to_numpy()
    return frame


def forecast_day(frame: pd.DataFrame, day: pd.Timestamp, model: str = "lear") -> np.ndarray | None:
    """LEAR ensemble (or, with ``model="lgbm"``, LightGBM) forecast of ``day``, or ``None``
    when an input is missing."""
    X, Y, dates = build_features(frame)
    t = int(np.flatnonzero(dates == day)[0])
    if not np.isfinite(X[t]).all():
        return None
    if model == "lgbm":
        return LGBM(**CONFIG).forecast_days(X, Y, np.array([t]), DEFAULT_SPEC)[0]
    return ensemble([LEAR(cw).forecast_day(X, Y, t, DEFAULT_SPEC) for cw in PAPER_WINDOWS])
