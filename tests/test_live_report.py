import numpy as np
import pandas as pd

from be_power_forecast.backtest import HOURS
from be_power_forecast.live_report import live_errors


def daily_file(path, days, value):
    frame = pd.DataFrame(value, pd.DatetimeIndex(days, name="Date"), HOURS)
    frame.to_csv(path)
    return path


def test_errors_since_the_first_live_day(tmp_path):
    days = pd.date_range("2026-09-24", "2026-10-07")
    # Realised prices: 100 every day, except 130 on Tuesday 2026-10-06.
    real = np.full((len(days), 24), 100.0)
    real[days.get_loc("2026-10-06")] = 130.0
    realised = daily_file(tmp_path / "realised.csv", days, real)
    live = pd.date_range("2026-10-01", "2026-10-07")
    files = {
        "lear": daily_file(tmp_path / "lear.csv", live, 110.0),  # always 10 too high
        "dnn": daily_file(tmp_path / "dnn.csv", live[:-1], 100.0),  # no forecast of 10-07
        "lgbm": daily_file(tmp_path / "lgbm.csv", live[1:], 95.0),  # none of 10-01
    }
    out = live_errors(files, realised, "2026-10-01")

    daily = out["daily"].set_index("day")
    assert len(daily) == 7 and pd.isna(daily.loc[pd.Timestamp("2026-10-07"), "dnn"])
    # Tuesday copies Monday (100): 30 off on 10-06; Wednesday copies Tuesday (130).
    assert daily.loc[pd.Timestamp("2026-10-06"), "naive"] == 30
    assert daily.loc[pd.Timestamp("2026-10-07"), "naive"] == 30
    assert daily.loc[pd.Timestamp("2026-10-06"), "lear"] == 20

    assert daily.loc[pd.Timestamp("2026-10-06"), "lgbm"] == 35

    # The summary only keeps the 5 days where every model has a forecast.
    summary = out["summary"].set_index("model")
    assert (summary["days"] == 5).all()
    assert summary.loc["lear", "since_start"] == (4 * 10 + 20) / 5
    assert summary.loc["dnn", "since_start"] == 30 / 5
    assert summary.loc["lgbm", "since_start"] == (4 * 5 + 35) / 5
    assert list(out["by_hour"]["hour"]) == list(range(24))
