import numpy as np
import pandas as pd
import pytest

from be_power_forecast.evaluation.attribution import (
    hour_segments,
    mae_gap_attribution,
    regime_segments,
    season_segments,
    spike_thresholds,
)


@pytest.mark.parametrize("seed", range(5))
def test_contributions_sum_to_mae_gap(seed):
    rng = np.random.default_rng(seed)
    real = rng.normal(50, 20, (60, 24))
    a, b = real + rng.normal(0, 5, real.shape), real + rng.standard_t(3, real.shape) * 4
    segments = rng.choice(["x", "y", "z"], size=real.shape, p=[0.6, 0.3, 0.1])
    out = mae_gap_attribution(real, a, b, segments)
    gap = np.abs(a - real).mean() - np.abs(b - real).mean()
    assert abs(out.loc[["x", "y", "z"], "contribution"].sum() - gap) < 1e-10
    assert abs(out.loc["total", "gap"] - gap) < 1e-10
    assert abs(out.loc["total", "share"] - 1) < 1e-10
    assert out.loc["total", "hours"] == real.size


def test_two_segment_example_by_hand():
    real = np.zeros(4)
    a = np.array([1.0, 1.0, 1.0, 5.0])  # |errors| of A
    b = np.array([2.0, 2.0, 2.0, 1.0])  # |errors| of B
    seg = np.array(["normal", "normal", "normal", "spike"])
    out = mae_gap_attribution(real, a, b, seg)
    # MAE_A = 2, MAE_B = 1.75, gap = 0.25
    # normal: w = 3/4, gap = 1 - 2 = -1, c = -0.75; spike: w = 1/4, gap = 5 - 1 = 4, c = 1
    assert out.loc["normal", "contribution"] == pytest.approx(-0.75)
    assert out.loc["spike", "contribution"] == pytest.approx(1.0)
    assert out.loc["total", "gap"] == pytest.approx(0.25)
    assert out.loc["spike", "share"] == pytest.approx(4.0)


def test_calendar_segments():
    days = pd.DatetimeIndex(["2016-02-29", "2016-06-01", "2016-12-01"])
    assert (hour_segments(days)[1] == np.arange(24)).all()
    assert list(season_segments(days)[:, 0]) == ["DJF", "JJA", "DJF"]


def test_spike_threshold_uses_history_only():
    idx = pd.date_range("2020-01-01", periods=24 * 30, freq="h")
    history = pd.Series(np.arange(len(idx), dtype=float), index=idx)
    day = pd.Timestamp("2020-01-21")
    base = spike_thresholds(pd.DatetimeIndex([day]), history, window=10).iloc[0]
    tampered = history.copy()
    tampered.loc[day:] = 1e6  # target day and future
    assert spike_thresholds(pd.DatetimeIndex([day]), tampered, window=10).iloc[0] == base
    assert base == np.quantile(history.loc["2020-01-11":"2020-01-20 23:00"], 0.95)


def test_regimes():
    idx = pd.date_range("2020-01-01", periods=24 * 12, freq="h")
    history = pd.Series(np.tile(np.arange(24, dtype=float), 12), index=idx)  # 0..23
    real = pd.DataFrame([[-5.0] + [10.0] * 22 + [100.0]], index=[pd.Timestamp("2020-01-12")])
    labels = regime_segments(real, history, window=10)
    assert labels[0, 0] == "negative" and labels[0, 1] == "normal" and labels[0, 23] == "spike"
