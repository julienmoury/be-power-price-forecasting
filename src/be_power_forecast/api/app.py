"""Forecast service: serves the LEAR ensemble forecast of a delivery day, with a naive fallback.

Forecasts are computed in batch, never at request time: recalibrating the four LEAR windows
takes ~30 s of CPU per day. The service reads

* the LEAR forecasts already computed: the phase B backtest (one CSV per calibration
  window, each day calibrated only on the days before it) and, later, the daily live runs;
* the standard frame of prices, for the naive fallback.

``POST /forecast`` returns the LEAR ensemble when the day has one, otherwise the naive
forecast (the forecasts are missing or could not be read); it never calls ENTSO-E and holds
no API key. Paths come from ``BE_FORECAST_DIR`` and ``BE_FRAME_PATH``.
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

log = logging.getLogger(__name__)


def load_backtest_ensemble(directory: Path) -> pd.DataFrame:
    """LEAR ensemble of the four calibration windows, ``(n_days, 24)``, from their CSVs."""
    fcs = [
        pd.read_csv(Path(directory) / f"lear_cw{cw}.csv", index_col=0, parse_dates=True)
        for cw in PAPER_WINDOWS
    ]
    days = fcs[0].index
    for f in fcs[1:]:
        days = days.intersection(f.index)
    values = ensemble([f.loc[days, HOURS].to_numpy() for f in fcs])
    return pd.DataFrame(values, index=days, columns=HOURS)


def load_prices(path: Path) -> pd.DataFrame:
    """Daily ``(n_days, 24)`` prices of a standard frame (dropped days are NaN rows)."""
    return daily_prices(pd.read_parquet(path))


class ForecastRequest(BaseModel):
    delivery_day: dt.date


class ForecastResponse(BaseModel):
    delivery_day: dt.date
    model: str  # "lear_ensemble" | "naive_fallback"
    origin: str  # "backtest" (reconstructed, no look-ahead) | "naive"
    prices: list[float]  # EUR/MWh, hours 00:00..23:00 Brussels time (calendar.py rules)
    inputs_until: dt.date  # last day of prices the forecast depends on


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
) -> FastAPI:
    data: dict = {}

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        lear = data["lear"] = _safe(lear_loader, "LEAR forecasts")
        prices = data["prices"] = _safe(price_loader, "prices")
        # Last servable day: the last LEAR forecast, or the day after the last known prices.
        ends = []
        if lear is not None and len(lear):
            ends.append(lear.index[-1])
        if prices is not None and prices.notna().all(axis=1).any():
            ends.append(prices.dropna().index[-1] + pd.Timedelta(days=1))
        data["end"] = max(ends) if ends else None
        yield

    app = FastAPI(title="Belgian day-ahead price forecast", lifespan=lifespan)

    @app.get("/health")
    def health() -> dict:
        end = data["end"]
        return {
            "status": "ok" if end is not None else "degraded",
            "lear_forecasts": data["lear"] is not None,
            "prices": data["prices"] is not None,
            "first_day": first_day,
            "last_day": None if end is None else str(end.date()),
        }

    @app.post("/forecast", response_model=ForecastResponse)
    def forecast(req: ForecastRequest) -> ForecastResponse:
        day = pd.Timestamp(req.delivery_day)
        end = data["end"]
        if end is None:
            raise HTTPException(503, "no forecast or price data available")
        if not pd.Timestamp(first_day) <= day <= end:
            raise HTTPException(404, f"forecasts are served from {first_day} to {end.date()}")
        lear, prices = data["lear"], data["prices"]
        if lear is not None and day in lear.index:
            values = lear.loc[day].to_numpy()
            return ForecastResponse(
                delivery_day=req.delivery_day,
                model="lear_ensemble",
                origin="backtest",
                prices=values.tolist(),
                inputs_until=(day - pd.Timedelta(days=1)).date(),
            )
        source = naive_source_day(day)
        if prices is not None and source in prices.index:
            values = prices.loc[source].to_numpy()
            if np.isfinite(values).all():
                return ForecastResponse(
                    delivery_day=req.delivery_day,
                    model="naive_fallback",
                    origin="naive",
                    prices=values.tolist(),
                    inputs_until=source.date(),
                )
        raise HTTPException(503, f"no LEAR forecast and no price for {source.date()}")

    return app


app = create_app(
    lambda: load_backtest_ensemble(
        Path(os.environ.get("BE_FORECAST_DIR", RESULTS_DIR / "forecasts" / "phase_b"))
    ),
    lambda: load_prices(Path(os.environ.get("BE_FRAME_PATH", CACHE_DIR / "phase_b_FR.parquet"))),
)
