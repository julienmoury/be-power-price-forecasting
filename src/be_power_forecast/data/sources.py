"""Data sources for hourly day-ahead prices and exogenous forecasts.

Every source returns a *standard frame*: an hourly ``DatetimeIndex`` (24 rows per day,
starting at 00:00) and the columns ``Price`` followed by named exogenous columns.
The model code only depends on that contract, so adding a source (e.g. ENTSO-E) does
not require touching the model.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]
RAW_DIR = REPO_ROOT / "data" / "raw"

ZENODO_URL = "https://zenodo.org/records/4624805/files/{market}.csv"


class PriceSource(ABC):
    """Interface implemented by every data source."""

    @abstractmethod
    def load(self) -> pd.DataFrame:
        """Return the standard frame (``Price`` + exogenous columns, hourly index)."""


def validate_standard_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Check the standard-frame contract and return the frame unchanged."""
    if df.columns[0] != "Price":
        raise ValueError("first column must be 'Price'")
    if not isinstance(df.index, pd.DatetimeIndex):
        raise TypeError("index must be a DatetimeIndex")
    if df.index[0].hour != 0 or len(df) % 24 != 0:
        raise ValueError("frame must start at 00:00 and contain whole days")
    steps = df.index.to_series().diff().dropna().unique()
    if len(steps) != 1 or steps[0] != pd.Timedelta(hours=1):
        raise ValueError("index must be regular hourly")
    if df.isna().any().any():
        raise ValueError("frame contains missing values")
    return df


class EpftoolboxZenodoSource(PriceSource):
    """Benchmark datasets of Lago et al. (2021), published on Zenodo (record 4624805).

    For ``BE`` the columns are: day-ahead price in Belgium (EUR/MWh), and the day-ahead
    generation and system-load forecasts for France (MW) used as exogenous inputs in the
    paper. The file is read from ``data/raw/`` and downloaded there if missing.
    """

    EXOGENOUS_NAMES = {"BE": ["Generation forecast FR", "Load forecast FR"]}

    def __init__(self, market: str = "BE", raw_dir: Path | str = RAW_DIR):
        self.market = market
        self.path = Path(raw_dir) / f"{market}.csv"

    def load(self) -> pd.DataFrame:
        if not self.path.exists():
            self.path.parent.mkdir(parents=True, exist_ok=True)
            pd.read_csv(ZENODO_URL.format(market=self.market)).to_csv(self.path, index=False)
        df = pd.read_csv(self.path, index_col=0)
        df.index = pd.to_datetime(df.index)
        df.index.name = "Date"
        names = self.EXOGENOUS_NAMES.get(
            self.market, [f"Exogenous {i}" for i in range(1, df.shape[1])]
        )
        df.columns = ["Price", *names]
        return validate_standard_frame(df.astype(float))


class EntsoeSource(PriceSource):
    """ENTSO-E Transparency Platform source (phase B, needs ``ENTSOE_API_KEY``).

    Not exercised yet: no API key was available when this repository was built. Since
    1 October 2025 the SDAC day-ahead market clears in 15-minute products, so quarter-hour
    prices are averaged to hourly values to keep the 24-prices-per-day contract.
    """

    def __init__(
        self,
        start: str,
        end: str,
        price_zone: str = "BE",
        exogenous_zone: str = "BE",
        tz: str = "Europe/Brussels",
    ):
        self.start = pd.Timestamp(start, tz=tz)
        self.end = pd.Timestamp(end, tz=tz)
        self.price_zone = price_zone
        self.exogenous_zone = exogenous_zone

    def load(self) -> pd.DataFrame:
        api_key = os.environ.get("ENTSOE_API_KEY")
        if not api_key:
            raise RuntimeError("set the ENTSOE_API_KEY environment variable")
        from entsoe import EntsoePandasClient  # optional dependency

        client = EntsoePandasClient(api_key=api_key)
        price = client.query_day_ahead_prices(self.price_zone, start=self.start, end=self.end)
        load = client.query_load_forecast(self.exogenous_zone, start=self.start, end=self.end)
        gen = client.query_generation_forecast(self.exogenous_zone, start=self.start, end=self.end)
        frames = [
            price.rename("Price"),
            _first_column(gen, "Generation forecast"),
            _first_column(load, "Load forecast"),
        ]
        hourly = [f.resample("1h").mean() for f in frames]
        df = pd.concat(hourly, axis=1).dropna()
        # Local time has 23/25-hour days at DST changes; UTC keeps 24 regular steps per
        # day (days then run 01:00-00:00 CET instead of 00:00-24:00).
        df.index = df.index.tz_convert("UTC").tz_localize(None)
        df = df.loc[df.index.normalize()[0] + pd.Timedelta(days=1) :]
        n_full = (len(df) // 24) * 24
        return validate_standard_frame(df.iloc[:n_full])


def _first_column(obj: pd.Series | pd.DataFrame, name: str) -> pd.Series:
    if isinstance(obj, pd.DataFrame):
        obj = obj.iloc[:, 0]
    return obj.rename(name)


def train_test_split(df: pd.DataFrame, begin_test: str, end_test: str):
    """Split a standard frame into training history and test period (whole days)."""
    begin = pd.Timestamp(begin_test)
    end = pd.Timestamp(end_test) + pd.Timedelta(hours=23)
    return df.loc[: begin - pd.Timedelta(hours=1)], df.loc[begin:end]


# Test period of Lago et al. (2021) for BE: the last 2 x 364 days of the dataset.
BE_TEST_BEGIN = "2015-01-04"
BE_TEST_END = "2016-12-31"
