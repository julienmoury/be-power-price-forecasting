"""SMARD client on synthetic files (tests/fixtures/smard/, no network)."""

import json
from pathlib import Path

import pandas as pd

from be_power_forecast.data.smard import smard_prices

FIX = Path(__file__).parent / "fixtures" / "smard"


def get(name):
    return json.loads((FIX / f"{name}.json").read_text())


def test_quarter_hours_of_a_window_across_weekly_files():
    index = get("index_quarterhour")["timestamps"]
    start = pd.Timestamp(index[1], unit="ms", tz="UTC") - pd.Timedelta(hours=1)
    end = start + pd.Timedelta(hours=2)
    s = smard_prices(start, end, get=get)
    assert len(s) == 8 and s.index.tz is not None and s.index.is_monotonic_increasing
    assert s.index[0] == start and s.index[-1] == end - pd.Timedelta(minutes=15)
    # Last quarter-hour of the first weekly file, then first of the second one.
    assert (s.iloc[3], s.iloc[4]) == (73.75, 60.0)


def test_unpublished_values_are_left_out():
    index = get("index_quarterhour")["timestamps"]
    end = pd.Timestamp(index[1], unit="ms", tz="UTC") + pd.Timedelta(days=7)
    s = smard_prices(end - pd.Timedelta(hours=1), end, get=get)
    assert len(s) == 3  # the last quarter-hour is null in the file
