import numpy as np
import pandas as pd

from be_power_forecast.evaluation.metrics import mae
from be_power_forecast.models.challenger import lgbm_backtest, tune

FAST = {"num_leaves": 15, "learning_rate": 0.1, "n_estimators": 50}


def synthetic_frame(n_days=120, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2020-01-06", periods=24 * n_days, freq="h")
    hour = idx.hour.to_numpy()
    load = 50_000 + 8_000 * np.sin(np.pi * hour / 24) + rng.normal(0, 3_000, len(idx))
    price = 20 + 0.0008 * load + rng.normal(0, 1, len(idx))
    return pd.DataFrame({"Price": price, "Load": load}, index=idx)


def run(df, begin="2020-04-10", end="2020-04-25"):
    return lgbm_backtest(df, begin, end, FAST, calibration_window=56, n_jobs=1)


def test_challenger_does_not_see_target_day_or_future():
    df = synthetic_frame()
    base = run(df)
    for day in ["2020-04-10", "2020-04-13"]:  # first day of a block and mid-block
        tampered = df.copy()
        tampered.loc[day:, "Price"] += 1000
        tampered.loc[pd.Timestamp(day) + pd.Timedelta(days=1) :, "Load"] *= 3
        pd.testing.assert_series_equal(run(tampered).loc[day], base.loc[day])


def test_challenger_is_deterministic_and_retrains_weekly():
    df = synthetic_frame()
    a, b = run(df), run(df)
    pd.testing.assert_frame_equal(a, b)
    assert len(a) == 16
    parallel = lgbm_backtest(df, "2020-04-10", "2020-04-25", FAST, 56, n_jobs=2)
    pd.testing.assert_frame_equal(a, parallel)


def test_challenger_learns_exogenous_relation():
    df = synthetic_frame(n_days=230)
    fc = lgbm_backtest(df, "2020-07-24", "2020-08-22", FAST, calibration_window=182, n_jobs=1)
    price = df["Price"].to_numpy().reshape(-1, 24)
    real, yesterday = price[-30:], price[-31:-1]
    assert mae(real, fc.to_numpy()) < 0.6 * mae(real, yesterday)


def test_tune_returns_best_grid_point(monkeypatch):
    import be_power_forecast.models.challenger as ch

    monkeypatch.setattr(ch, "GRID", {"num_leaves": (4, 15), "n_estimators": (5, 50)})
    best, scores = tune(synthetic_frame(), "2020-04-10", "2020-04-20", 56, n_jobs=1)
    assert len(scores) == 4
    assert min(s["MAE"] for s in scores) == next(
        s["MAE"] for s in scores if {k: s[k] for k in best} == best
    )
