# Adapted from the code of Lago et al. (2021), by Jesus Lago (Apache-2.0)
# — changes: Keras 3 API (``learning_rate`` instead of ``lr``, no ``batch_input_shape`` on
# hidden layers, ``negative_slope`` for LeakyReLU); samples built with numpy index arithmetic
# instead of per-timestamp look-ups (same features, same order); the weekly validation
# shuffle vectorised (same permutation); hyperparameters read from a JSON extract of the
# published trial files; the numpy seed is set before the validation draw of every day
# (the original draws it from the state left by the previous day's seed, i.e. the same
# draw from the second day on) and Python/TensorFlow are seeded too (unseeded in the
# original); samples touching days dropped by the data rules are removed; the training
# history and a hash of the final weights are returned; no file I/O or printing.
"""DNN of Lago et al. (2021): a two-hidden-layer MLP that maps the selected inputs of a day
to its 24 prices, recalibrated every day on four years of data.

Inputs, network size, scaling, dropout, learning rate, activation and initialiser are those
chosen by hyperopt in the paper (one set per DNN of the ensemble, see
``data/raw/dnn_hyperparameters_BE.json``). Recalibration as in the original code: the last
4 x 364 days, minus one week of lags, give the samples; whole weeks are drawn at random
into a 25 % validation set; Adam on the MAE, batch 192, at most 1 000 epochs, early
stopping after 20 epochs without improvement of the validation loss or MAE, best weights
kept. With data augmentation, a sample starts at every hour instead of every midnight.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from be_power_forecast.config import RAW_DIR
from be_power_forecast.models.scaling import make_scaler

HYPERPARAMETERS = RAW_DIR / "dnn_hyperparameters_BE.json"
CALIBRATION_DAYS = 4 * 364
LAG_DAYS = 7  # the first week of the window only serves as lags
PRICE_LAGS = (1, 2, 3, 7)
EXOGENOUS_LAGS = (1, 7)
VALIDATION_SHARE = 0.25
BATCH_SIZE = 192
MAX_EPOCHS = 1000
PATIENCE = 20


def load_hyperparameters(path: Path | str = HYPERPARAMETERS) -> dict[str, dict]:
    """Published settings of each DNN of the ensemble, keyed by trial-file suffix."""
    return json.loads(Path(path).read_text())


@dataclass(frozen=True)
class HourlyInputs:
    """Hourly arrays of a standard frame: prices, exogenous series, day of week."""

    price: np.ndarray  # (n_hours,)
    exog: np.ndarray  # (n_hours, n_exog)
    dow: np.ndarray  # (n_hours,)
    dates: pd.DatetimeIndex  # one per day

    @classmethod
    def from_frame(cls, df: pd.DataFrame) -> HourlyInputs:
        dates = pd.DatetimeIndex(df.index[::24])
        return cls(
            price=df["Price"].to_numpy(float),
            exog=df.iloc[:, 1:].to_numpy(float),
            dow=np.repeat(dates.dayofweek.to_numpy(), 24).astype(float),
            dates=dates,
        )


def forecastable(inputs: HourlyInputs) -> np.ndarray:
    """Days whose own data and every possible input day (d-1, d-2, d-3, d-7) are complete.

    The same days as the LEAR backtest: days that depend on a day dropped by the data rules
    are not forecast, whatever inputs a DNN selects.
    """
    n = len(inputs.dates)
    daily = np.column_stack([inputs.price.reshape(n, 24), inputs.exog.reshape(n, -1)])
    complete = np.isfinite(daily).all(axis=1)
    ok = complete.copy()
    for k in sorted({*PRICE_LAGS, *EXOGENOUS_LAGS}):
        ok[k:] &= complete[:-k]
        ok[:k] = False
    return ok


def build_samples(inputs: HourlyInputs, hp: dict, starts: np.ndarray):
    """Inputs ``X`` and 24 prices ``Y`` of the samples starting at the hours ``starts``.

    Feature order of the original: day of week (+ hour / 24 for augmented samples); for each
    hour, the selected price lags; for each hour, the selected exogenous lags then the
    selected exogenous values of the day itself.
    """
    hours = starts[:, None] + np.arange(24)  # (n, 24)
    blocks = []
    if hp["In: Day"]:
        blocks.append((inputs.dow[starts] + starts % 24 / 24)[:, None])
    lags = [k for k in PRICE_LAGS if hp[f"In: Price D-{k}"]]
    if lags:
        idx = hours[:, :, None] - 24 * np.array(lags)  # (n, 24, n_lags)
        blocks.append(inputs.price[idx].reshape(len(starts), -1))
    n_exog = inputs.exog.shape[1]
    exog = [(k, e) for k in EXOGENOUS_LAGS for e in range(n_exog) if hp[f"In: Exog-{e + 1} D-{k}"]]
    exog += [(0, e) for e in range(n_exog) if hp[f"In: Exog-{e + 1} D"]]
    if exog:
        k, e = (np.array(v) for v in zip(*exog, strict=True))
        blocks.append(inputs.exog[hours[:, :, None] - 24 * k, e].reshape(len(starts), -1))
    return np.hstack(blocks), inputs.price[hours]


def validation_split(n: int) -> tuple[np.ndarray, np.ndarray]:
    """Shuffle whole weeks of samples (global numpy state) and keep the last 25 % for validation.

    For augmented samples a "week" is 7 consecutive hourly samples, as in the original.
    """
    n_val = int(VALIDATION_SHARE * n)
    weeks = np.arange(0, n, 7)
    np.random.shuffle(weeks)
    order = (weeks[:, None] + np.arange(7)).ravel()
    order = order[order < n]
    return order[: n - n_val], order[n - n_val :]


def build_network(n_features: int, hp: dict):
    """Keras MLP of the original ``DNNModel``, compiled with Adam on the MAE."""
    import keras
    from keras import layers

    activation = hp["activation"]
    init = "lecun_normal" if activation == "selu" else hp["init"]
    reg = keras.regularizers.l1(hp["lambdal1"]) if hp["reg"] == "l1" else None
    sizes = [int(hp[f"neurons{k}"]) for k in (1, 2, 3, 4, 5) if f"neurons{k}" in hp]
    inp = x = keras.Input(batch_shape=(None, n_features))
    for size in (s for s in sizes if s >= 50):  # smaller layers are dropped, as in the original
        if activation in ("LeakyReLU", "PReLU"):
            x = layers.Dense(
                size, activation="linear", kernel_initializer=init, kernel_regularizer=reg
            )(x)
            x = (
                layers.LeakyReLU(negative_slope=0.001)(x)
                if activation == "LeakyReLU"
                else (layers.PReLU()(x))
            )
        else:
            x = layers.Dense(
                size, activation=activation, kernel_initializer=init, kernel_regularizer=reg
            )(x)
        if hp["batch_normalization"]:
            x = layers.BatchNormalization()(x)
        if hp["dropout"] > 0:
            dropout = layers.AlphaDropout if activation == "selu" else layers.Dropout
            x = dropout(hp["dropout"])(x)
    out = layers.Dense(24, kernel_initializer=init, kernel_regularizer=reg)(x)
    model = keras.Model(inputs=[inp], outputs=[out])
    model.compile(
        loss="mae", optimizer=keras.optimizers.Adam(learning_rate=hp["lr"], clipvalue=10000)
    )
    return model


def _original_scale(scaler, Y: np.ndarray) -> np.ndarray:
    return Y if scaler is None else scaler.inverse_transform(Y)


def fit(model, scaler_y, Xtrain, Ytrain, Xval, Yval) -> list[tuple[float, float, float]]:
    """Train epoch by epoch with the original early stopping; keep the best weights.

    Returns the history: per epoch, training loss, validation loss and validation MAE
    (in EUR/MWh).
    """
    best_error = best_mae = 1e20
    no_improvement = 0
    best_weights = model.get_weights()
    history = []
    for _ in range(MAX_EPOCHS):
        fitted = model.fit(Xtrain, Ytrain, batch_size=BATCH_SIZE, epochs=1, verbose=0, shuffle=True)
        val_error = model.evaluate(Xval, Yval, verbose=0)
        Ybar = model.predict(Xval, verbose=0)
        val_mae = float(
            np.mean(np.abs(_original_scale(scaler_y, Yval) - _original_scale(scaler_y, Ybar)))
        )
        history.append((float(fitted.history["loss"][0]), float(val_error), val_mae))
        if val_error < best_error:
            no_improvement = 0
            best_weights = model.get_weights()
            best_error, best_mae = val_error, val_mae
        elif val_mae < best_mae:
            no_improvement = 0
            best_weights = model.get_weights()
            best_mae = val_mae
        else:
            no_improvement += 1
        if no_improvement >= PATIENCE:
            break
    model.set_weights(best_weights)
    return history


def weights_sha256(weights: list[np.ndarray]) -> str:
    digest = hashlib.sha256()
    for w in weights:
        digest.update(np.ascontiguousarray(w).tobytes())
    return digest.hexdigest()


def forecast_day(inputs: HourlyInputs, t: int, setting: dict):
    """Recalibrate one DNN on the window before day ``t`` and forecast day ``t``.

    ``setting`` is one entry of :func:`load_hyperparameters`. Returns the 24 prices, a record
    of the training (sizes, seed, history, hashes) and the final weights.
    """
    import keras

    hp = setting["hyperparameters"]
    seed = int(hp["seed"])
    first = (t - CALIBRATION_DAYS + LAG_DAYS) * 24
    if first < LAG_DAYS * 24:
        raise ValueError("not enough history for the 4-year calibration window")
    step = 1 if setting["data_augmentation"] else 24
    starts = np.arange(first, (t - 1) * 24 + 1, step)
    X, Y = build_samples(inputs, hp, starts)
    Xtest, _ = build_samples(inputs, hp, np.array([t * 24]))
    if not np.isfinite(Xtest).all():
        raise ValueError("inputs of the forecast day are missing")
    np.random.seed(seed)
    train, val = validation_split(len(starts))
    # Samples touching days dropped by the data rules leave the sample (none in BE.csv).
    ok = np.isfinite(X).all(axis=1) & np.isfinite(Y).all(axis=1)
    train, val = train[ok[train]], val[ok[val]]
    Xtrain, Xval, Ytrain, Yval = X[train], X[val], Y[train], Y[val]
    scaler_x = make_scaler(hp["scaleX"])
    if scaler_x is not None:
        Xtrain = scaler_x.fit_transform(Xtrain)
        Xval, Xtest = scaler_x.transform(Xval), scaler_x.transform(Xtest)
    scaler_y = make_scaler(hp["scaleY"])
    if scaler_y is not None:
        Ytrain = scaler_y.fit_transform(Ytrain)
        Yval = scaler_y.transform(Yval)

    keras.utils.set_random_seed(seed)  # numpy (as the original), Python and TensorFlow
    model = build_network(X.shape[1], hp)
    history = fit(model, scaler_y, Xtrain, Ytrain, Xval, Yval)
    forecast = _original_scale(scaler_y, model.predict(Xtest, verbose=0).reshape(1, -1))[0]
    weights = model.get_weights()
    keras.backend.clear_session()

    window = slice((t - CALIBRATION_DAYS) * 24, t * 24)
    record = {
        "date": str(inputs.dates[t].date()),
        "seed": seed,
        "n_features": int(X.shape[1]),
        "n_train": len(train),
        "n_val": len(val),
        "validation_sha256": hashlib.sha256(starts[val].tobytes()).hexdigest(),
        "data_sha256": hashlib.sha256(
            np.ascontiguousarray(inputs.price[window]).tobytes()
            + np.ascontiguousarray(inputs.exog[window]).tobytes()
            + np.ascontiguousarray(inputs.exog[t * 24 : (t + 1) * 24]).tobytes()
        ).hexdigest(),
        "epochs": len(history),
        "best_epoch": _best_epoch(history),
        "history": history,
        "weights_sha256": weights_sha256(weights),
        "forecast": [float(v) for v in forecast],
    }
    return forecast, record, weights


def _best_epoch(history) -> int:
    """1-based epoch whose weights were kept (last epoch that reset the patience counter)."""
    best_error = best_mae = 1e20
    best = 0
    for epoch, (_, error, mae) in enumerate(history, start=1):
        if error < best_error:
            best_error, best_mae, best = error, mae, epoch
        elif mae < best_mae:
            best_mae, best = mae, epoch
    return best
