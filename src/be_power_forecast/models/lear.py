# Adapted from the code of Lago et al. (2021), by Jesus Lago (Apache-2.0)
# — changes: feature matrix built once for the whole history with numpy reshapes instead of
# per-day timestamp look-ups (same features, same order); configurable price/exogenous lags
# for ablation studies; the LassoLarsIC(criterion="aic", normalize=True) selection of the
# original (scikit-learn < 1.2) is re-implemented on top of `lars_path` because that
# estimator changed in later scikit-learn versions; no file I/O or printing.
"""LEAR: LASSO-Estimated AutoRegressive model for day-ahead prices (Uniejewski et al., 2016).

One LASSO regression per delivery hour. Inputs for day ``d`` and hour ``h``:

* prices of all 24 hours of days ``d-1, d-2, d-3, d-7``;
* every exogenous series at all 24 hours of days ``d-1, d-7`` and ``d`` (forecasts are known
  before the day-ahead auction closes);
* 7 day-of-week dummies.

Prices and inputs are asinh-median transformed; the LASSO penalty is chosen by AIC along
the LARS path, then the model is refitted by coordinate descent with that penalty.
"""

from __future__ import annotations

import warnings
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import Lasso, LassoLarsIC, lars_path

from be_power_forecast.models.scaling import InvariantScaler

N_DUMMIES = 7
# Days at the start of each calibration window used only as lags (one week, as in the
# original), kept fixed so that ablations change the inputs but not the sample size.
WINDOW_BUFFER = 7


@dataclass(frozen=True)
class FeatureSpec:
    """Which lags enter the LEAR design matrix (defaults = Lago et al., 2021)."""

    price_lags: tuple[int, ...] = (1, 2, 3, 7)
    exogenous_lags: tuple[int, ...] = (1, 7, 0)

    @property
    def max_lag(self) -> int:
        return max((*self.price_lags, *self.exogenous_lags, 0))


DEFAULT_SPEC = FeatureSpec()


def to_daily(series: pd.Series | np.ndarray) -> np.ndarray:
    """Reshape an hourly series into a ``(n_days, 24)`` array."""
    values = np.asarray(series, dtype=float)
    if values.size % 24:
        raise ValueError("hourly series must contain whole days")
    return values.reshape(-1, 24)


def build_features(df: pd.DataFrame, spec: FeatureSpec = DEFAULT_SPEC):
    """Build the LEAR design matrix for every day of a standard frame.

    Returns ``(X, Y, dates)`` where row ``t`` of ``X`` holds the inputs for day ``dates[t]``
    and ``Y[t]`` its 24 prices. Rows ``t < spec.max_lag`` reference data before the start of
    the frame and are filled with NaN.
    """
    price = to_daily(df["Price"])
    exog = [to_daily(df[c]) for c in df.columns[1:]]
    n_days = price.shape[0]
    dates = pd.DatetimeIndex(df.index[::24])

    def lag(a: np.ndarray, k: int) -> np.ndarray:
        out = np.full_like(a, np.nan)
        out[k:] = a[: n_days - k] if k else a
        return out

    blocks = []
    # Price block: for each hour, for each lag (feature order of the original code).
    price_lagged = np.stack([lag(price, k) for k in spec.price_lags], axis=2)  # (n, 24, L)
    blocks.append(price_lagged.reshape(n_days, -1))
    # Exogenous block: for each hour, for each lag, for each exogenous series.
    if exog:
        ex = np.stack(
            [np.stack([lag(e, k) for e in exog], axis=2) for k in spec.exogenous_lags], axis=2
        )  # (n, 24, n_lags, n_exog)
        blocks.append(ex.reshape(n_days, -1))
    dummies = np.zeros((n_days, N_DUMMIES))
    dummies[np.arange(n_days), dates.dayofweek] = 1.0
    blocks.append(dummies)
    return np.hstack(blocks), price, dates


def _aic_alpha_legacy(X: np.ndarray, y: np.ndarray, max_iter: int = 2500) -> float:
    """Penalty chosen by ``LassoLarsIC(criterion="aic", normalize=True)`` in scikit-learn < 1.2.

    Columns are centred and scaled to unit L2 norm, the LASSO-LARS path is computed, and the
    criterion ``n * MSE / var(y) + 2 * df`` is minimised along the path.
    """
    X = X - X.mean(axis=0)
    norms = np.sqrt((X**2).sum(axis=0))
    norms[norms == 0] = 1.0
    X = X / norms
    y = y - y.mean()
    alphas, _, coefs = lars_path(
        X,
        y,
        Gram="auto",
        alpha_min=0.0,
        method="lasso",
        max_iter=max_iter,
        eps=np.finfo(float).eps,
    )
    residuals = y[:, None] - X @ coefs
    mse = np.mean(residuals**2, axis=0)
    df = (np.abs(coefs) > np.finfo(float).eps).sum(axis=0)
    criterion = len(y) * mse / (np.var(y) + np.finfo(np.float64).eps) + 2 * df
    return float(alphas[np.argmin(criterion)])


def _aic_alpha_current(X: np.ndarray, y: np.ndarray, max_iter: int = 2500) -> float:
    """Penalty chosen by the scikit-learn >= 1.2 ``LassoLarsIC`` (no normalisation)."""
    return float(LassoLarsIC(criterion="aic", max_iter=max_iter).fit(X, y).alpha_)


ALPHA_SELECTORS = {"legacy": _aic_alpha_legacy, "sklearn": _aic_alpha_current}


class LEAR:
    """Daily-recalibrated LEAR model.

    Parameters
    ----------
    calibration_window : int
        Number of days of history used at each recalibration.
    alpha_selection : {"legacy", "sklearn"}
        ``"legacy"`` reproduces the penalty selection used to produce the published results.
    """

    def __init__(self, calibration_window: int = 364 * 3, alpha_selection: str = "legacy"):
        self.calibration_window = calibration_window
        self.select_alpha = ALPHA_SELECTORS[alpha_selection]

    def recalibrate(self, X: np.ndarray, Y: np.ndarray) -> LEAR:
        X = np.array(X, dtype=float)
        self.scaler_y = InvariantScaler()
        Y = self.scaler_y.fit_transform(Y)
        self.scaler_x = InvariantScaler()
        X[:, :-N_DUMMIES] = self.scaler_x.fit_transform(X[:, :-N_DUMMIES])
        self.models = []
        self.alphas = []
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", ConvergenceWarning)
            for h in range(Y.shape[1]):
                alpha = self.select_alpha(X, Y[:, h])
                self.models.append(Lasso(alpha=alpha, max_iter=2500).fit(X, Y[:, h]))
                self.alphas.append(alpha)
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        X = np.array(np.atleast_2d(X), dtype=float)
        X[:, :-N_DUMMIES] = self.scaler_x.transform(X[:, :-N_DUMMIES])
        Yp = np.column_stack([m.predict(X) for m in self.models])
        return self.scaler_y.inverse_transform(Yp)

    def n_selected_features(self) -> np.ndarray:
        """Number of non-zero coefficients per hour (after the last recalibration)."""
        return np.array([(m.coef_ != 0).sum() for m in self.models])

    def forecast_day(self, X: np.ndarray, Y: np.ndarray, t: int, spec: FeatureSpec) -> np.ndarray:
        """Recalibrate on the window ending the day before ``t`` and forecast day ``t``.

        Mirrors the original: the window holds ``calibration_window`` days of data, and its
        first week only serves as lags, so ``calibration_window - 7`` training samples are used.
        """
        first = t - self.calibration_window + WINDOW_BUFFER
        if first < max(spec.max_lag, WINDOW_BUFFER):
            raise ValueError("not enough history for this calibration window")
        # Days dropped by the data rules (NaN rows or lags) leave the sample; none in BE.csv.
        ok = np.isfinite(X[first:t]).all(axis=1) & np.isfinite(Y[first:t]).all(axis=1)
        self.recalibrate(X[first:t][ok], Y[first:t][ok])
        return self.predict(X[t])[0]


def ensemble(forecasts: Sequence[np.ndarray]) -> np.ndarray:
    """Arithmetic mean of several forecasts (the 'LEAR Ensemble' of Lago et al.)."""
    return np.mean(np.stack(forecasts), axis=0)
