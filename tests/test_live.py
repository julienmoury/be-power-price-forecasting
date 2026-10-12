import numpy as np
import pandas as pd

from be_power_forecast.backtest import HOURS
from be_power_forecast.live import forecast_day, live_frame, score
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


def test_naive_forecast_when_a_french_forecast_is_not_published():
    frame = live_frame(raw(DAY - pd.Timedelta(days=1)), DAY)
    model, values = forecast_day(frame, DAY)
    assert model == "naive_fallback"
    expected = frame.loc[DAY - pd.Timedelta(days=1) : DAY - pd.Timedelta(hours=1), "Price"]
    assert np.allclose(values, expected.to_numpy())


def test_score_only_days_with_known_prices():
    days = pd.date_range("2026-10-05", "2026-10-14")  # Monday to Wednesday of next week
    prices = pd.DataFrame(np.arange(len(days) * 24.0).reshape(-1, 24), days, HOURS)
    forecasts = pd.DataFrame(
        {"origin": "live", "model": "lear_ensemble", **{h: 0.0 for h in HOURS}},
        index=pd.DatetimeIndex(["2026-10-13", "2026-10-15"], name="Date"),
    )
    out = score(forecasts, prices)
    assert list(out.index) == [pd.Timestamp("2026-10-13")]  # 2026-10-15 not delivered yet
    real = prices.loc["2026-10-13"]
    assert out.loc["2026-10-13", "MAE"] == real.mean()
    assert out.loc["2026-10-13", "MAE naive"] == 24.0  # Tuesday copies Monday: gap of 24
    assert out.loc["2026-10-13", "origin"] == "live"
