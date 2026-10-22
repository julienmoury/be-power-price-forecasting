"""DNN port: samples identical to the original code, early stopping, seeding, records.

tests/reference/original_dnn_samples.json holds the SHA-256 of the training, validation
and test arrays built by the paper's *original* code (scripts/make_original_dnn_reference.py
--samples); they depend on the data only, not on the machine.
"""

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from be_power_forecast.data.sources import LagoZenodoSource
from be_power_forecast.models import dnn
from be_power_forecast.models.scaling import InvariantScaler, MedianScaler, make_scaler

REF = Path(__file__).parent / "reference"
SAMPLES = json.loads((REF / "original_dnn_samples.json").read_text())


@pytest.fixture(scope="module")
def inputs():
    return dnn.HourlyInputs.from_frame(LagoZenodoSource("BE").load())


def test_published_hyperparameters():
    settings = dnn.load_hyperparameters()
    assert list(settings) == ["SF", "SF_DA", "SF_SF", "SF_SF_DA"]
    assert [int(s["hyperparameters"]["seed"]) for s in settings.values()] == [650, 842, 178, 553]
    assert [s["data_augmentation"] for s in settings.values()] == [False, True, False, True]


def _sha(a):
    return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()


@pytest.mark.parametrize("key", sorted(SAMPLES))
def test_samples_match_original_code(inputs, key):
    name, day = key.split()
    setting = dnn.load_hyperparameters()[name]
    hp = setting["hyperparameters"]
    t = inputs.dates.get_loc(pd.Timestamp(day))
    first = (t - dnn.CALIBRATION_DAYS + dnn.LAG_DAYS) * 24
    starts = np.arange(first, (t - 1) * 24 + 1, 1 if setting["data_augmentation"] else 24)
    X, Y = dnn.build_samples(inputs, hp, starts)
    Xtest, _ = dnn.build_samples(inputs, hp, np.array([t * 24]))
    np.random.seed(int(hp["seed"]))
    train, val = dnn.validation_split(len(starts))
    arrays = {"Xtrain": X[train], "Ytrain": Y[train], "Xval": X[val], "Yval": Y[val]}
    arrays["Xtest"] = Xtest
    for part, (shape, sha) in SAMPLES[key].items():
        assert list(arrays[part].shape) == shape, part
        assert _sha(arrays[part]) == sha, part


def test_scalers():
    rng = np.random.default_rng(2026)
    x = rng.normal(50, 20, (200, 3))
    for scaler in (MedianScaler(), InvariantScaler(), make_scaler("Norm1"), make_scaler("Std")):
        np.testing.assert_allclose(scaler.inverse_transform(scaler.fit_transform(x)), x)
    assert make_scaler("No") is None
    z = MedianScaler().fit_transform(x)
    np.testing.assert_allclose(np.median(z, axis=0), 0, atol=1e-12)


class ScriptedModel:
    """Stands for a Keras model whose validation loss and MAE follow a script."""

    def __init__(self, losses, maes):
        self.losses, self.maes, self.epoch = list(losses), list(maes), 0

    def fit(self, *args, **kwargs):
        self.epoch += 1
        return type("History", (), {"history": {"loss": [1.0]}})()

    def evaluate(self, *args, **kwargs):
        return self.losses[self.epoch - 1]

    def predict(self, X, **kwargs):
        return np.full((len(X), 24), self.maes[self.epoch - 1])

    def get_weights(self):
        return [np.array(self.epoch)]

    def set_weights(self, weights):
        self.kept = int(weights[0])


def test_early_stopping_as_original(monkeypatch):
    monkeypatch.setattr(dnn, "PATIENCE", 3)
    # Epoch 2 improves the loss, epoch 4 only the MAE: the patience restarts at both.
    losses = [5, 4, 4.5, 4.2, 6, 6, 6, 6, 6]
    maes = [5, 4, 4.5, 3.5, 6, 6, 6, 6, 6]
    model = ScriptedModel(losses, maes)
    history = dnn.fit(model, None, None, None, np.zeros((2, 1)), np.zeros((2, 24)))
    assert len(history) == 7 and model.kept == 4
    assert dnn._best_epoch(history) == 4


def test_training_is_seeded_and_recorded(monkeypatch):
    monkeypatch.setattr(dnn, "MAX_EPOCHS", 2)
    rng = np.random.default_rng(2026)
    days = dnn.CALIBRATION_DAYS + 1
    index = pd.date_range("2020-01-06", periods=days * 24, freq="h")
    exog = rng.normal([5e4, 6e4], 1e3, (len(index), 2))
    df = pd.DataFrame({"Price": 40 + 10 * rng.standard_normal(len(index))}, index=index)
    df[["Exogenous 1", "Exogenous 2"]] = exog
    inputs = dnn.HourlyInputs.from_frame(df)
    setting = dnn.load_hyperparameters()["SF"]
    f1, r1, w1 = dnn.forecast_day(inputs, days - 1, setting)
    f2, r2, _ = dnn.forecast_day(inputs, days - 1, setting)
    np.testing.assert_array_equal(f1, f2)
    assert r1["weights_sha256"] == r2["weights_sha256"] == dnn.weights_sha256(w1)
    assert r1["epochs"] == len(r1["history"]) == 2 and r1["n_train"] + r1["n_val"] == 1449
    assert r1["date"] == str(inputs.dates[-1].date()) and len(r1["forecast"]) == 24


def test_forecastable_days_skip_dropped_inputs():
    days = 20
    index = pd.date_range("2020-01-06", periods=days * 24, freq="h")
    df = pd.DataFrame({"Price": 1.0, "Exogenous 1": 2.0}, index=index)
    df.iloc[10 * 24 : 11 * 24, 1] = np.nan  # day 10 dropped (exogenous missing)
    ok = dnn.forecastable(dnn.HourlyInputs.from_frame(df))
    assert not ok[:7].any()  # no d-7 input yet
    assert [t for t in range(7, days) if not ok[t]] == [10, 11, 12, 13, 17]
