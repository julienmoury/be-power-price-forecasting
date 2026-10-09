from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from be_power_forecast.backtest import lear_backtest
from be_power_forecast.data.calendar import hourly_mean, standard_frame, to_local_days
from be_power_forecast.data.entsoe_parser import parse_generation, parse_loads, parse_prices
from be_power_forecast.data.sources import EntsoeSource, validate_standard_frame

FIXTURES = Path(__file__).parent / "fixtures" / "entsoe"


def read(name: str) -> str:
    return (FIXTURES / name).read_text()


def test_spring_dst_day_interpolates_missing_hour():
    load = parse_loads(read("load_A65_dst_spring.xml"))
    assert len(load) == 23
    days, report = to_local_days(load)
    assert list(days.index) == [pd.Timestamp("2025-03-30")]
    row = days.iloc[0]
    assert row[2] == (row[1] + row[3]) / 2
    assert row[3] == load.iloc[2]  # local 03:00 CEST = 01:00 UTC, third value
    assert report["dst_23h_days"] == 1 and report["dropped_days"] == []


def test_autumn_dst_day_averages_repeated_hour():
    load = parse_loads(read("load_A65_dst_autumn.xml"))
    assert len(load) == 25
    days, report = to_local_days(load)
    row = days.iloc[0]
    # 02:00 CEST = 00:00 UTC and 02:00 CET = 01:00 UTC
    assert row[2] == (load.iloc[2] + load.iloc[3]) / 2
    assert row[3] == load.iloc[4] and row[23] == load.iloc[24]
    assert report["dst_25h_days"] == 1 and not days.isna().any().any()


def test_quarter_hour_prices_are_averaged_to_hours():
    prices = parse_prices(read("prices_A44_quarter_hour.xml"))["15min"]
    days, report = to_local_days(prices)
    assert list(days.index) == [pd.Timestamp("2025-10-02")]
    np.testing.assert_allclose(days.iloc[0].to_numpy(), prices.to_numpy().reshape(24, 4).mean(1))
    assert report["dropped_days"] == []


def test_missing_quarter_hour_or_hour_drops_the_day():
    prices = parse_prices(read("prices_A44_hourly.xml"))["60min"]
    days, report = to_local_days(prices.drop(prices.index[30]))  # an hour of 15 Jan
    assert report["dropped_days"] == ["2025-01-15"]
    assert days.loc["2025-01-15"].isna().all() and not days.loc["2025-01-14"].isna().any()
    quarter = parse_prices(read("prices_A44_quarter_hour.xml"))["15min"]
    assert hourly_mean(quarter.drop(quarter.index[9])).isna().sum() == 1


def test_standard_frame_from_mixed_resolutions():
    series = {
        "Price": parse_prices(read("prices_A44_hourly.xml"))["60min"],
        "Generation forecast FR": parse_generation(read("generation_A71.xml"))["Actual Aggregated"],
        "Wind and solar forecast BE": parse_generation(read("wind_solar_A69.xml")).sum(axis=1),
    }
    frame, report = standard_frame(series)
    validate_standard_frame(frame)
    assert frame.index[0] == pd.Timestamp("2025-01-14 00:00") and len(frame) == 48
    assert frame.iloc[0, 0] == series["Price"].iloc[0]  # 00:00 local = 23:00 UTC the day before
    assert report["dropped_days_any_series"] == []


def test_day_missing_in_one_series_is_dropped_in_all():
    price = pd.Series(
        np.arange(24 * 5, dtype=float),
        index=pd.date_range("2025-01-01", periods=24 * 5, freq="h", tz="Europe/Brussels"),
    ).tz_convert("UTC")
    exog = price.drop(price.index[24 * 2 + 5])
    frame, report = standard_frame({"Price": price, "Load forecast FR": exog})
    assert report["dropped_days_any_series"] == ["2025-01-03"]
    assert frame.loc["2025-01-03"].isna().all().all() and len(frame) == 24 * 5
    validate_standard_frame(frame, allow_missing_days=True)
    with pytest.raises(ValueError):
        validate_standard_frame(frame)


class FakeClient:
    def __init__(self, series):
        self.series, self.calls = series, []

    def query(self, kind, area, start, end):
        self.calls.append((kind, area))
        return self.series[(kind, area)]


def test_entsoe_source_uses_french_exogenous_set_and_cache(tmp_path):
    series = {
        ("prices", "BE"): parse_prices(read("prices_A44_hourly.xml"))["60min"],
        ("generation", "FR"): parse_generation(read("generation_A71.xml"))["Actual Aggregated"],
        ("load", "FR"): parse_generation(read("generation_A71.xml"))["Actual Aggregated"] / 2,
    }
    client = FakeClient(series)
    source = EntsoeSource("2025-01-14", "2025-01-15", cache_dir=tmp_path, client=client)
    frame = source.load()
    assert list(frame.columns) == ["Price", "Generation forecast FR", "Load forecast FR"]
    assert len(frame) == 48 and len(list(tmp_path.glob("*.parquet"))) == 3
    again = EntsoeSource("2025-01-14", "2025-01-15", cache_dir=tmp_path, client=client).load()
    assert len(client.calls) == 3  # second load reads the cache
    pd.testing.assert_frame_equal(frame, again)


def test_backtest_skips_dropped_days():
    rng = np.random.default_rng(0)
    n_days = 120
    index = pd.date_range("2020-01-01", periods=24 * n_days, freq="h")
    exog = rng.normal(size=len(index))
    df = pd.DataFrame({"Price": 50 + 5 * exog + rng.normal(size=len(index)), "X": exog}, index)
    df.loc["2020-03-01"] = np.nan  # a dropped day inside the calibration window
    df.loc["2020-04-20"] = np.nan  # a dropped day inside the test period
    fc = lear_backtest(df, "2020-04-15", "2020-04-25", calibration_window=56, n_jobs=1)
    # The dropped day and the days using it as a d-1, d-2 or d-3 lag are not forecast.
    skipped = pd.date_range("2020-04-20", "2020-04-23")
    assert fc.index.intersection(skipped).empty
    assert len(fc) == 11 - 4 and np.isfinite(fc.to_numpy()).all()


def test_resolution_change_is_handled_hour_by_hour():
    hourly = pd.Series(1.0, index=pd.date_range("2025-09-29 22:00", periods=24, freq="h", tz="UTC"))
    quarter = pd.Series(
        np.arange(96, dtype=float),
        index=pd.date_range("2025-09-30 22:00", periods=96, freq="15min", tz="UTC"),
    )
    days, report = to_local_days(pd.concat([hourly, quarter]))
    assert report["dropped_days"] == [] and len(days) == 2
    assert days.iloc[0].eq(1.0).all() and days.iloc[1, 0] == 1.5
