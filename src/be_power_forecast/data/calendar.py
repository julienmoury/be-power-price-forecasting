"""Local Brussels delivery days: hourly averaging, DST rules and dropped days.

A market day is a local delivery day (00:00-24:00 Europe/Brussels). Rules:

* sub-hourly values (15-minute products since 1 October 2025) are averaged to hours; an
  hour not fully covered (e.g. a missing quarter-hour) is missing;
* 23-hour day (last Sunday of March): the missing 02:00 is linearly interpolated from
  01:00 and 03:00;
* 25-hour day (last Sunday of October): the two occurrences of 02:00 are averaged;
* a day with any other gap is dropped (kept as a row of NaN so that day lags stay aligned)
  and reported.
"""

from __future__ import annotations

import pandas as pd

from be_power_forecast.config import TZ

HOURS = list(range(24))


def hourly_mean(series: pd.Series) -> pd.Series:
    """Average a UTC-indexed series to hours; an hour not fully covered is NaN.

    Each value covers its own resolution (the step to its neighbours), so a series whose
    resolution changes (hourly to 15-minute) is handled hour by hour.
    """
    series = series.dropna()
    steps = series.index.to_series().diff()
    step = pd.concat([steps, steps.shift(-1)], axis=1).min(axis=1)
    covered = step.clip(upper=pd.Timedelta("1h")).fillna(pd.Timedelta("1h"))
    complete = covered.resample("1h").sum() == pd.Timedelta("1h")
    return series.resample("1h").mean().where(complete)


def hours_in_day(days: pd.DatetimeIndex) -> pd.Series:
    """Number of hours of each local delivery day (23, 24 or 25)."""
    start = days.tz_localize(TZ)
    end = (days + pd.Timedelta(days=1)).tz_localize(TZ)
    return pd.Series(((end - start) / pd.Timedelta("1h")).astype(int), index=days)


def to_local_days(series: pd.Series) -> tuple[pd.DataFrame, dict]:
    """``(n_days, 24)`` frame of local delivery days from a UTC-indexed series.

    Every calendar day between the first and the last day is present; dropped days are rows
    of NaN. The report counts the DST days handled and lists the dropped days.
    """
    hourly = hourly_mean(series.sort_index()).tz_convert(TZ)
    day = hourly.index.tz_localize(None).normalize()
    present = hourly.notna().groupby(day).sum()
    days = pd.date_range(day.min(), day.max(), freq="D")
    expected = hours_in_day(days)
    complete = present.reindex(days, fill_value=0) == expected
    # groupby(day, hour).mean() averages the two 02:00 of a 25-hour day.
    frame = hourly.groupby([day, hourly.index.hour]).mean().unstack().reindex(days)
    frame = frame.reindex(columns=HOURS)
    spring = expected.index[(expected == 23) & complete]
    frame.loc[spring, 2] = (frame.loc[spring, 1] + frame.loc[spring, 3]) / 2
    frame.loc[~complete.to_numpy()] = float("nan")
    report = {
        "days": len(days),
        "dst_23h_days": int(len(spring)),
        "dst_25h_days": int(((expected == 25) & complete).sum()),
        "dropped_days": [d.strftime("%Y-%m-%d") for d in days[~complete.to_numpy()]],
    }
    return frame, report


def standard_frame(series: dict[str, pd.Series]) -> tuple[pd.DataFrame, dict]:
    """Standard frame (naive local hourly index) from UTC series; first key must be ``Price``.

    The frame covers the days common to all series; a day missing in any series is a row of
    NaN in all of them. Returns the frame and a per-series report.
    """
    daily, report = {}, {}
    for name, s in series.items():
        daily[name], report[name] = to_local_days(s)
    first = max(d.index[0] for d in daily.values())
    last = min(d.index[-1] for d in daily.values())
    daily = {k: d.loc[first:last].copy() for k, d in daily.items()}
    missing = pd.concat([d.isna().any(axis=1) for d in daily.values()], axis=1).any(axis=1)
    kept = missing.index[~missing]  # trim incomplete days at both ends
    missing = missing.loc[kept[0] : kept[-1]]
    for d in daily.values():
        d.loc[missing.index[missing]] = float("nan")
    index = pd.DatetimeIndex(
        [d + pd.Timedelta(hours=h) for d in missing.index for h in HOURS], name="Date"
    )
    columns = {k: d.loc[missing.index].to_numpy().ravel() for k, d in daily.items()}
    frame = pd.DataFrame(columns, index=index)
    report["dropped_days_any_series"] = [d.strftime("%Y-%m-%d") for d in missing.index[missing]]
    return frame, report
