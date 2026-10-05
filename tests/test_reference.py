"""The adapted building blocks reproduce the original epftoolbox code.

References in tests/reference/ were produced by running the *original* epftoolbox code
(commit 47d6e06) under scikit-learn 0.23.2; see scripts/make_original_*.py.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from be_power_forecast.data.sources import EpftoolboxZenodoSource
from be_power_forecast.evaluation.dm import dm_test
from be_power_forecast.evaluation.metrics import mae, rmae, smape
from be_power_forecast.models.lear import LEAR, FeatureSpec, build_features

REF = Path(__file__).parent / "reference"


@pytest.fixture(scope="module")
def features():
    df = EpftoolboxZenodoSource("BE").load()
    X, Y, dates = build_features(df)
    return X, Y, {d: i for i, d in enumerate(dates)}


@pytest.fixture(scope="module")
def published():
    f = pd.read_csv(REF / "Forecasts_BE_DNN_LEAR_ensembles.csv", index_col=0, parse_dates=True)
    daily = {c: f[c].to_numpy().reshape(-1, 24) for c in f.columns}
    index = pd.DatetimeIndex(f.index[::24])
    return {c: pd.DataFrame(v, index=index) for c, v in daily.items()}


def _original_lear_cases(windows):
    ref = pd.read_csv(REF / "original_lear_reference.csv")
    ref = ref[ref.calibration_window.isin(windows)]
    return [
        (int(r.calibration_window), r.date, r.iloc[2:].to_numpy(float)) for _, r in ref.iterrows()
    ]


@pytest.mark.parametrize("cw,date,expected", _original_lear_cases([56, 84]))
def test_lear_matches_original_code_short_windows(features, cw, date, expected):
    X, Y, pos = features
    forecast = LEAR(cw).forecast_day(X, Y, pos[pd.Timestamp(date)], FeatureSpec())
    np.testing.assert_allclose(forecast, expected, atol=1e-6)


@pytest.mark.slow
@pytest.mark.parametrize("cw,date,expected", _original_lear_cases([1092, 1456]))
def test_lear_matches_original_code_long_windows(features, cw, date, expected):
    X, Y, pos = features
    forecast = LEAR(cw).forecast_day(X, Y, pos[pd.Timestamp(date)], FeatureSpec())
    np.testing.assert_allclose(forecast, expected, atol=1e-6)


def test_metrics_match_original_code(published):
    ref = json.loads((REF / "original_metrics_reference.json").read_text())
    real = published["Real price"]
    for name in ["LEAR 56", "LEAR 84", "LEAR 1092", "LEAR 1456", "LEAR Ensemble", "DNN Ensemble"]:
        pred = published[name]
        assert mae(real, pred) == pytest.approx(ref[name]["MAE"], rel=1e-12)
        assert smape(real, pred) == pytest.approx(ref[name]["sMAPE"], rel=1e-12)
        assert rmae(real, pred) == pytest.approx(ref[name]["rMAE"], rel=1e-12)
        assert rmae(real, pred, m="W") == pytest.approx(ref[name]["rMAE_W"], rel=1e-12)
        assert rmae(real, pred, m="D") == pytest.approx(ref[name]["rMAE_D"], rel=1e-12)


def test_published_mae_values_of_the_paper(published):
    # MAE reported for BE in Lago et al. (2021): LEAR ensemble 6.14, DNN ensemble 5.87.
    real = published["Real price"]
    assert mae(real, published["LEAR Ensemble"]) == pytest.approx(6.14, abs=0.005)
    assert mae(real, published["DNN Ensemble"]) == pytest.approx(5.87, abs=0.005)


def test_dm_matches_original_code(published):
    ref = json.loads((REF / "original_metrics_reference.json").read_text())
    real = published["Real price"]
    lear, dnn = published["LEAR Ensemble"], published["DNN Ensemble"]
    _, p_uni = dm_test(real, lear, dnn, norm=1, version="univariate")
    np.testing.assert_allclose(p_uni, ref["DM_LEARens_vs_DNNens_univariate_norm1"], rtol=1e-9)
    _, p = dm_test(real, lear, dnn, norm=1, version="multivariate")
    assert p == pytest.approx(ref["DM_LEARens_vs_DNNens_multivariate_norm1"], rel=1e-9)
    _, p = dm_test(real, published["LEAR 56"], lear, norm=2, version="multivariate")
    assert p == pytest.approx(ref["DM_LEAR56_vs_LEARens_multivariate_norm2"], rel=1e-9)
