import json

import numpy as np
from test_units import synthetic_frame

from be_power_forecast.config import REPO_ROOT
from be_power_forecast.models.lear import FeatureSpec, build_features
from be_power_forecast.models.lgbm import CONFIG, LGBM, lgbm_backtest

SMALL = {"calibration_window": 56, "num_leaves": 7, "learning_rate": 0.1, "n_estimators": 20}


def test_lgbm_does_not_see_target_day():
    X, Y, _ = build_features(synthetic_frame(80))
    days = np.array([70, 71])
    base = LGBM(**SMALL).forecast_days(X, Y, days, FeatureSpec())
    Y2 = Y.copy()
    Y2[70:] += 1000  # tamper with the forecast days and the future
    assert np.array_equal(LGBM(**SMALL).forecast_days(X, Y2, days, FeatureSpec()), base)


def test_backtest_retrains_every_k_days_and_runs_in_parallel():
    df = synthetic_frame(100)
    X, Y, dates = build_features(df)
    begin = dates[80]
    weekly = lgbm_backtest(df, str(begin), str(dates[93]), SMALL, retrain_every=7, n_jobs=1)
    assert len(weekly) == 14 and weekly.index[0] == begin
    # The second week is forecast by the models trained on the days before it.
    second = LGBM(**SMALL).forecast_days(X, Y, np.arange(87, 94), FeatureSpec())
    np.testing.assert_array_equal(weekly.iloc[7:].to_numpy(), second)
    daily = lgbm_backtest(df, str(begin), str(dates[83]), SMALL, n_jobs=2)
    one = LGBM(**SMALL).forecast_days(X, Y, np.array([82]), FeatureSpec())[0]
    np.testing.assert_array_equal(daily.iloc[2].to_numpy(), one)
    assert np.mean(np.abs(daily.to_numpy() - Y[80:84])) < 4.0  # noise std is 2


def test_frozen_configuration_is_the_best_of_the_tuning():
    tuning = json.loads((REPO_ROOT / "results" / "lgbm_tuning.json").read_text())
    assert len(tuning["scores"]) == np.prod([len(v) for v in tuning["grid"].values()])
    assert tuning["tuning_period"][1] < "2017-01-01"
    best = min(tuning["scores"], key=lambda s: s["MAE"])
    assert CONFIG == {k: best[k] for k in tuning["grid"]}
