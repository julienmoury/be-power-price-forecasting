"""Forecast service: the LEAR ensemble forecast of a delivery day, with a naive fallback,
and the DNN ensemble and LightGBM forecasts next to it.

Forecasts are computed in batch, never at request time: recalibrating the four LEAR windows
takes ~30 s of CPU per day. The service reads

* the LEAR and DNN forecasts already computed: the phase B backtests (one CSV per
  calibration window or DNN, each day calibrated only on the days before it) and the daily
  live forecasts (``scripts/live_forecast.py``);
* the Belgian prices (price-only standard frame), for the naive fallback.

``POST /forecast`` returns the LEAR ensemble when the day has one, otherwise the naive
forecast (the forecasts are missing or could not be read), and the DNN ensemble in
``dnn_prices`` and the LightGBM forecast in ``lgbm_prices`` when the day has them (shown
next to the LEAR, never averaged with it);
``GET /forecasts`` does the same for a range of days. The service runs locally with the
user's own ENTSO-E data (the naive forecast is a copy of past prices); it never calls
ENTSO-E and holds no API key. Paths come from ``BE_FORECAST_DIR``, ``BE_LIVE_PATH``,
``BE_DNN_LIVE_PATH``, ``BE_LGBM_LIVE_PATH`` and ``BE_PRICE_PATH``. Its OpenAPI schema is kept in
``docs/openapi.json`` (``scripts/export_openapi.py``).
"""

from __future__ import annotations

import datetime as dt
import logging
import os
from collections.abc import Callable
from contextlib import asynccontextmanager
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from be_power_forecast.backtest import HOURS, daily_prices
from be_power_forecast.config import CACHE_DIR, PAPER_WINDOWS, PHASE_B_TEST, RESULTS_DIR
from be_power_forecast.evaluation.metrics import naive_source_day
from be_power_forecast.models.lear import ensemble

DNNS = ("SF", "SF_DA", "SF_SF", "SF_SF_DA")  # the four DNNs of the ensemble

log = logging.getLogger(__name__)


def load_forecasts(directory: Path, names, live_path: Path | None = None) -> pd.DataFrame:
    """Ensemble forecasts by day (24 hours), each calibrated on the days before it.

    The mean of the backtest CSVs ``<name>.csv`` of ``directory``, followed by the days
    forecast by the daily live run.
    """
    fcs = [pd.read_csv(Path(directory) / f"{n}.csv", index_col=0, parse_dates=True) for n in names]
    days = fcs[0].index
    for f in fcs[1:]:
        days = days.intersection(f.index)
    out = pd.DataFrame(ensemble([f.loc[days, HOURS].to_numpy() for f in fcs]), days, HOURS)
    if live_path is not None and Path(live_path).exists():
        live = pd.read_csv(live_path, index_col=0, parse_dates=True)[HOURS]
        out = pd.concat([out.drop(index=live.index, errors="ignore"), live]).sort_index()
    return out


def load_lear_forecasts(directory: Path, live_path: Path | None = None) -> pd.DataFrame:
    """LEAR ensemble: the mean of the four calibration windows, then the live days."""
    return load_forecasts(directory, [f"lear_cw{cw}" for cw in PAPER_WINDOWS], live_path)


def load_dnn_forecasts(directory: Path, live_path: Path | None = None) -> pd.DataFrame:
    """DNN ensemble: the mean of the four DNNs, then the live days."""
    return load_forecasts(directory, [f"dnn_{n}" for n in DNNS], live_path)


def load_lgbm_forecasts(directory: Path, live_path: Path | None = None) -> pd.DataFrame:
    """LightGBM challenger: its backtest, then the live days."""
    return load_forecasts(directory, ["lgbm"], live_path)


def load_prices(path: Path) -> pd.DataFrame:
    """Daily ``(n_days, 24)`` prices of a standard frame (missing days are NaN rows)."""
    return daily_prices(pd.read_parquet(path))


class ForecastRequest(BaseModel):
    delivery_day: dt.date


class ForecastResponse(BaseModel):
    delivery_day: dt.date
    model: str  # "lear_ensemble" | "naive_fallback"
    prices: list[float]  # EUR/MWh, hours 00:00..23:00 Brussels time (calendar.py rules)
    inputs_until: dt.date  # last day of prices the forecast depends on
    dnn_prices: list[float] | None = None  # DNN ensemble of the day, when there is one
    lgbm_prices: list[float] | None = None  # LightGBM of the day, when there is one


def _safe(loader: Callable[[], pd.DataFrame], name: str) -> pd.DataFrame | None:
    try:
        return loader()
    except Exception:  # a missing or unreadable source means fallback, not a crash
        log.exception("could not load %s", name)
        return None


def create_app(
    lear_loader: Callable[[], pd.DataFrame],
    price_loader: Callable[[], pd.DataFrame],
    first_day: str = PHASE_B_TEST[0],
    dnn_loader: Callable[[], pd.DataFrame] | None = None,
    lgbm_loader: Callable[[], pd.DataFrame] | None = None,
) -> FastAPI:
    data: dict = {}

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        lear = data["lear"] = _safe(lear_loader, "LEAR forecasts")
        prices = data["prices"] = _safe(price_loader, "prices")
        data["dnn"] = None if dnn_loader is None else _safe(dnn_loader, "DNN forecasts")
        data["lgbm"] = None if lgbm_loader is None else _safe(lgbm_loader, "LightGBM forecasts")
        # Last servable day: the last LEAR forecast, or the day after the last known prices.
        ends = []
        if lear is not None and len(lear):
            ends.append(lear.index[-1])
        if prices is not None and prices.notna().all(axis=1).any():
            ends.append(prices.dropna().index[-1] + pd.Timedelta(days=1))
        data["end"] = max(ends) if ends else None
        yield

    app = FastAPI(title="Belgian day-ahead price forecast", version="1.0", lifespan=lifespan)

    def resolve(day: pd.Timestamp) -> ForecastResponse | None:
        """LEAR ensemble of ``day``, else its naive forecast, else ``None``; with its DNN
        ensemble and LightGBM forecast when there are."""
        answer = _resolve(day)
        for name in ("dnn", "lgbm"):
            other = data[name]
            if answer is not None and other is not None and day in other.index:
                values = other.loc[day, HOURS].to_numpy(dtype=float).tolist()
                setattr(answer, f"{name}_prices", values)
        return answer

    def _resolve(day: pd.Timestamp) -> ForecastResponse | None:
        lear, prices = data["lear"], data["prices"]
        if lear is not None and day in lear.index:
            return ForecastResponse(
                delivery_day=day.date(),
                model="lear_ensemble",
                prices=lear.loc[day, HOURS].to_numpy(dtype=float).tolist(),
                inputs_until=(day - pd.Timedelta(days=1)).date(),
            )
        source = naive_source_day(day)
        if prices is not None and source in prices.index:
            values = prices.loc[source].to_numpy()
            if np.isfinite(values).all():
                return ForecastResponse(
                    delivery_day=day.date(),
                    model="naive_fallback",
                    prices=values.tolist(),
                    inputs_until=source.date(),
                )
        return None

    def check_range(first: pd.Timestamp, last: pd.Timestamp) -> None:
        end = data["end"]
        if end is None:
            raise HTTPException(503, "no forecast or price data available")
        if not pd.Timestamp(first_day) <= first <= last <= end:
            raise HTTPException(404, f"forecasts are served from {first_day} to {end.date()}")

    @app.get("/health")
    def health() -> dict:
        end = data["end"]
        return {
            "status": "ok" if end is not None else "degraded",
            "lear_forecasts": data["lear"] is not None,
            "dnn_forecasts": data["dnn"] is not None,
            "lgbm_forecasts": data["lgbm"] is not None,
            "prices": data["prices"] is not None,
            "first_day": first_day,
            "last_day": None if end is None else str(end.date()),
        }

    @app.post("/forecast", response_model=ForecastResponse)
    def forecast(req: ForecastRequest) -> ForecastResponse:
        day = pd.Timestamp(req.delivery_day)
        check_range(day, day)
        answer = resolve(day)
        if answer is None:
            source = naive_source_day(day).date()
            raise HTTPException(503, f"no LEAR forecast and no price for {source}")
        return answer

    @app.get("/forecasts", response_model=list[ForecastResponse])
    def forecasts(start: dt.date, end: dt.date) -> list[ForecastResponse]:
        """Forecasts of the days ``start`` to ``end`` (included); days with neither a LEAR
        forecast nor a naive reference are left out."""
        first, last = pd.Timestamp(start), pd.Timestamp(end)
        check_range(first, last)
        answers = (resolve(day) for day in pd.date_range(first, last))
        return [a for a in answers if a is not None]

    return app


app = create_app(
    lambda: load_lear_forecasts(
        Path(os.environ.get("BE_FORECAST_DIR", RESULTS_DIR / "forecasts" / "phase_b")),
        Path(os.environ.get("BE_LIVE_PATH", RESULTS_DIR / "forecasts" / "live" / "forecasts.csv")),
    ),
    lambda: load_prices(Path(os.environ.get("BE_PRICE_PATH", CACHE_DIR / "prices_BE.parquet"))),
    dnn_loader=lambda: load_dnn_forecasts(
        Path(os.environ.get("BE_FORECAST_DIR", RESULTS_DIR / "forecasts" / "phase_b")),
        Path(
            os.environ.get(
                "BE_DNN_LIVE_PATH", RESULTS_DIR / "forecasts" / "live" / "dnn_forecasts.csv"
            )
        ),
    ),
    lgbm_loader=lambda: load_lgbm_forecasts(
        Path(os.environ.get("BE_FORECAST_DIR", RESULTS_DIR / "forecasts" / "phase_b")),
        Path(
            os.environ.get(
                "BE_LGBM_LIVE_PATH", RESULTS_DIR / "forecasts" / "live" / "lgbm_forecasts.csv"
            )
        ),
    ),
)
