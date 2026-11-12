import numpy as np
import pandas as pd

from be_power_forecast.live import forecast_day, live_frame
from be_power_forecast.models.lear import build_features

DAY = pd.Timestamp("2015-03-10")  # Tuesday: the naive forecast copies the day before


def utc_hours(first_local_day, last_local_day, value):
    start = pd.Timestamp(first_local_day, tz="Europe/Brussels").tz_convert("UTC")
    end = (pd.Timestamp(last_local_day, tz="Europe/Brussels") + pd.Timedelta(days=1)).tz_convert(
        "UTC"
    )
    index = pd.date_range(start, end, freq="h", inclusive="left")
    rng = np.random.default_rng(2026)
    return pd.Series(value + rng.normal(0, 1, len(index)), index=index)


def raw(exog_until):
    # ENTSO-E part of the joined frame starts on JOIN_DAY (2015-01-05); BE.csv before.
    return {
        "Price": utc_hours("2015-01-05", DAY - pd.Timedelta(days=1), 40.0),
        "Generation forecast FR": utc_hours("2015-01-05", exog_until, 60000.0),
        "Load forecast FR": utc_hours("2015-01-05", exog_until, 55000.0),
    }


def test_live_frame_holds_the_inputs_of_the_delivery_day():
    frame = live_frame(raw(DAY), DAY)
    assert frame.index[-1] == DAY + pd.Timedelta(hours=23)
    assert frame.loc[DAY:, "Price"].isna().all()
    assert frame.loc[DAY:, ["Generation forecast FR", "Load forecast FR"]].notna().all().all()
    X, _, dates = build_features(frame)
    assert np.isfinite(X[dates == DAY]).all()  # the LEAR ensemble can forecast the day


def test_no_forecast_when_a_french_forecast_is_not_published():
    # Never the naive forecast: it is a copy of past prices, which are not published.
    frame = live_frame(raw(DAY - pd.Timedelta(days=1)), DAY)
    assert forecast_day(frame, DAY) is None
    assert forecast_day(frame, DAY, "lgbm") is None
