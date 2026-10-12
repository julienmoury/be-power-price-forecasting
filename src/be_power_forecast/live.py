"""Daily live forecast: update the ENTSO-E series, forecast the next delivery day, score.

Run every morning by ``scripts/live_forecast.py`` (GitHub Actions, needs ENTSOE_API_KEY),
before the 12:00 gate closure of the day-ahead auction. The model and its inputs are those
of the backtests; only our forecasts and daily errors are written to the repository, the
raw ENTSO-E data stay in the cache.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from be_power_forecast.backtest import HOURS, daily_prices
from be_power_forecast.config import EXOGENOUS, PAPER_WINDOWS, TZ
from be_power_forecast.data.calendar import standard_frame, to_local_days
from be_power_forecast.data.entsoe_client import EntsoeClient
from be_power_forecast.data.sources import EntsoeSource, JoinedSource, PriceSource
from be_power_forecast.evaluation.metrics import mae, naive_source_day
from be_power_forecast.models.lear import DEFAULT_SPEC, LEAR, build_features, ensemble

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


def forecast_day(frame: pd.DataFrame, day: pd.Timestamp) -> tuple[str, np.ndarray] | None:
    """LEAR ensemble forecast of ``day``, or the naive forecast when an input is missing."""
    X, Y, dates = build_features(frame)
    t = int(np.flatnonzero(dates == day)[0])
    if np.isfinite(X[t]).all():
        fcs = [LEAR(cw).forecast_day(X, Y, t, DEFAULT_SPEC) for cw in PAPER_WINDOWS]
        return "lear_ensemble", ensemble(fcs)
    prices = daily_prices(frame)
    source = naive_source_day(day)
    if source in prices.index and prices.loc[source].notna().all():
        return "naive_fallback", prices.loc[source].to_numpy()
    return None


def score(forecasts: pd.DataFrame, prices: pd.DataFrame) -> pd.DataFrame:
    """Daily MAE of each live forecast and of the naive forecast, once prices are known."""
    rows = {}
    for day, row in forecasts.iterrows():
        source = naive_source_day(day)
        if day not in prices.index or source not in prices.index:
            continue
        real, naive = prices.loc[day], prices.loc[source]
        if real.notna().all() and naive.notna().all():
            pred = row[HOURS].to_numpy(dtype=float)
            rows[day] = {
                "model": row["model"],
                "MAE": mae(real, pred),
                "MAE naive": mae(real, naive),
            }
    out = pd.DataFrame.from_dict(rows, orient="index", columns=["model", "MAE", "MAE naive"])
    out.index.name = "Date"
    return out
