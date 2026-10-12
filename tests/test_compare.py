import numpy as np
import pandas as pd

from be_power_forecast.data.compare import compare, largest_daily_gaps, local_hourly, monthly


def hourly(days: int, start: str = "2016-01-01") -> pd.Series:
    index = pd.date_range(start, periods=24 * days, freq="h")
    return pd.Series(np.sin(np.arange(len(index)) / 3.0) * 10 + 50, index=index)


def test_identical_series_agree_exactly():
    s = hourly(3)
    r = compare(s, s.copy())
    assert r["hours"] == 72 and r["share_equal_pct"] == 100.0
    assert r["mae"] == 0.0 and r["best_shift_hours"] == 0


def test_offset_gives_bias_and_mae():
    s = hourly(3)
    r = compare(s, s - 2.0)
    assert np.isclose(r["bias"], 2.0) and np.isclose(r["mae"], 2.0)
    assert r["share_equal_pct"] == 0.0


def test_one_hour_misalignment_is_detected():
    s = hourly(3)
    assert compare(s, s.shift(-1))["best_shift_hours"] == 1


def test_only_common_hours_are_compared():
    s = hourly(3)
    other = s.copy()
    other.iloc[:24] = np.nan
    assert compare(s, other)["hours"] == 48


def test_monthly_and_largest_days():
    s = hourly(40, start="2016-01-15")
    other = s.copy()
    other.loc["2016-02-10 05:00"] += 7.0
    m = monthly(s, other)
    assert list(m.index.astype(str)) == ["2016-01", "2016-02"]
    assert m.loc["2016-01", "mae"] == 0.0
    top = largest_daily_gaps(s, other, n=1)
    assert top.index[0] == pd.Timestamp("2016-02-10") and top.iloc[0] == 7.0


def test_local_hourly_converts_utc_to_brussels_days():
    utc = pd.date_range("2015-12-31 23:00", periods=48, freq="h", tz="UTC")
    s = pd.Series(np.arange(48.0), index=utc, name="x")
    local, report = local_hourly(s)
    assert local.index[0] == pd.Timestamp("2016-01-01 00:00")
    assert local.iloc[0] == 0.0 and len(local) == 48
    assert report["dropped_days"] == []
