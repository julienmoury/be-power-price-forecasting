"""Errors of the live forecasts since the first live day, computed in SQL (DuckDB).

The forecast and realised-price files (one row per day, columns h0..h23) are loaded into
two long tables, ``forecasts`` and ``realised``; the queries are in ``sql/``.
"""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path

import duckdb
import pandas as pd

from be_power_forecast.backtest import HOURS

SQL = files("be_power_forecast") / "sql"


def long_format(path: Path) -> pd.DataFrame:
    """A daily file (Date, h0..h23) as rows of (day, hour, price)."""
    wide = pd.read_csv(path, index_col=0, parse_dates=True)[HOURS]
    out = wide.rename_axis("day").reset_index().melt("day", var_name="hour", value_name="price")
    out["day"] = out["day"].dt.date
    out["hour"] = out["hour"].str[1:].astype(int)
    return out.dropna()


def live_errors(forecast_files: dict[str, Path], realised_file: Path, start: str) -> dict:
    """Daily, summary and by-hour errors of the models of ``forecast_files``."""
    forecasts = pd.concat(
        [long_format(path).assign(model=model) for model, path in forecast_files.items()]
    )
    con = duckdb.connect()
    con.register("forecasts", forecasts[["model", "day", "hour", "price"]])
    con.register("realised", long_format(realised_file))
    con.execute((SQL / "errors.sql").read_text().format(start=start))
    queries = ("daily", "summary", "by_hour")
    return {name: con.sql((SQL / f"{name}.sql").read_text()).df() for name in queries}
