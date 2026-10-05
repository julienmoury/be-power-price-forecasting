import numpy as np
import pandas as pd
import pytest

from be_power_forecast.data.sources import validate_standard_frame
from be_power_forecast.evaluation.dm import dm_test
from be_power_forecast.evaluation.metrics import mae, naive_forecast, rmae, smape
from be_power_forecast.models.lear import LEAR, FeatureSpec, build_features
from be_power_forecast.models.scaling import InvariantScaler


def synthetic_frame(n_days=120, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2020-01-06", periods=24 * n_days, freq="h")  # a Monday
    hour = idx.hour.to_numpy()
    load = 50_000 + 8_000 * np.sin(np.pi * hour / 24) + rng.normal(0, 500, len(idx))
    price = 20 + 0.0008 * load + rng.normal(0, 2, len(idx))
    return pd.DataFrame({"Price": price, "Load": load}, index=idx)


def test_invariant_scaler_roundtrip():
    x = np.random.default_rng(1).lognormal(3, 1, size=(200, 5))
    s = InvariantScaler()
    np.testing.assert_allclose(s.inverse_transform(s.fit_transform(x)), x, rtol=1e-10)


def test_feature_layout():
    df = synthetic_frame(20)
    X, Y, dates = build_features(df)
    # 24 hours x 4 price lags + 24 hours x 3 lags x 1 exogenous + 7 dummies
    assert X.shape == (20, 96 + 72 + 7)
    t = 10
    price, load = Y, df["Load"].to_numpy().reshape(-1, 24)
    assert X[t, 0] == price[t - 1, 0] and X[t, 3] == price[t - 7, 0]  # hour 0, lags 1 and 7
    assert X[t, 4] == price[t - 1, 1]  # hour 1, lag 1
    assert X[t, 96] == load[t - 1, 0] and X[t, 98] == load[t, 0]  # exog lags 1, 7, 0
    assert X[t, -7 + dates[t].dayofweek] == 1 and X[t, -7:].sum() == 1
    assert np.isnan(X[:7, :96]).any(axis=1).all() and not np.isnan(X[7:]).any()


def test_lear_does_not_see_target_day():
    df = synthetic_frame(80)
    X, Y, _ = build_features(df)
    t = 70
    base = LEAR(56).forecast_day(X, Y, t, FeatureSpec())
    Y2 = Y.copy()
    Y2[t:] += 1000  # tamper with the target day and the future
    assert np.allclose(LEAR(56).forecast_day(X, Y2, t, FeatureSpec()), base)


def test_lear_learns_linear_relation():
    df = synthetic_frame(150)
    X, Y, _ = build_features(df)
    fc = np.array([LEAR(84).forecast_day(X, Y, t, FeatureSpec()) for t in range(120, 150)])
    assert mae(Y[120:150], fc) < 3.0  # noise std is 2


def test_naive_forecast_rules():
    idx = pd.date_range("2021-01-04", periods=21, freq="D")  # starts on a Monday
    prices = pd.DataFrame(np.arange(21)[:, None] * np.ones((1, 24)), index=idx)
    naive = naive_forecast(prices)
    assert naive.index[0] == idx[7]
    for day, row in naive.iterrows():
        lag = 7 if day.dayofweek in (0, 5, 6) else 1
        assert row.iloc[0] == prices.loc[day - pd.Timedelta(days=lag)].iloc[0]


def test_metrics_basic():
    real = np.array([[10.0, 20.0]])
    pred = np.array([[12.0, 20.0]])
    assert mae(real, pred) == 1.0
    assert smape(real, pred) == pytest.approx((2 / 11) / 2)
    idx = pd.date_range("2021-01-04", periods=14, freq="D")
    p = pd.DataFrame(np.random.default_rng(0).normal(50, 5, (14, 24)), index=idx)
    assert rmae(p, naive_forecast(p, "D").reindex(idx).fillna(p), m="D") >= 0


def test_dm_detects_better_forecast():
    rng = np.random.default_rng(0)
    real = rng.normal(50, 10, (300, 24))
    good = real + rng.normal(0, 1, real.shape)
    bad = real + rng.normal(0, 3, real.shape)
    _, p = dm_test(real, bad, good)
    assert p < 0.01
    _, p = dm_test(real, good, bad)
    assert p > 0.99


def test_standard_frame_validation():
    df = synthetic_frame(3)
    validate_standard_frame(df)
    with pytest.raises(ValueError):
        validate_standard_frame(df.iloc[1:])
    with pytest.raises(ValueError):
        validate_standard_frame(df.rename(columns={"Price": "p"}))
