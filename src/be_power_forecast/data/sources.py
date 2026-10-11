"""Data sources for hourly day-ahead prices and exogenous forecasts.

Every source returns a *standard frame*: an hourly ``DatetimeIndex`` (24 rows per day,
starting at 00:00) and the columns ``Price`` followed by named exogenous columns.
The model code only depends on that contract, so adding a source (e.g. ENTSO-E) does
not require touching the model.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

import pandas as pd

from be_power_forecast.config import (
    CACHE_DIR,
    EXOGENOUS,
    PHASE_A_TEST,
    PHASE_B_DOWNLOAD,
    RAW_DIR,
)
from be_power_forecast.data.calendar import standard_frame
from be_power_forecast.data.entsoe_client import EntsoeClient

ZENODO_URL = "https://zenodo.org/records/4624805/files/{market}.csv"


class PriceSource(ABC):
    """Interface implemented by every data source."""

    @abstractmethod
    def load(self) -> pd.DataFrame:
        """Return the standard frame (``Price`` + exogenous columns, hourly index)."""


def validate_standard_frame(df: pd.DataFrame, allow_missing_days: bool = False) -> pd.DataFrame:
    """Check the standard-frame contract and return the frame unchanged.

    With ``allow_missing_days``, missing values are accepted only as whole days missing in
    every column (days dropped by the rules of ``data/calendar.py``).
    """
    if df.columns[0] != "Price":
        raise ValueError("first column must be 'Price'")
    if not isinstance(df.index, pd.DatetimeIndex):
        raise TypeError("index must be a DatetimeIndex")
    if df.index[0].hour != 0 or len(df) % 24 != 0:
        raise ValueError("frame must start at 00:00 and contain whole days")
    steps = df.index.to_series().diff().dropna().unique()
    if len(steps) != 1 or steps[0] != pd.Timedelta(hours=1):
        raise ValueError("index must be regular hourly")
    day_missing = df.isna().to_numpy().reshape(-1, 24 * df.shape[1])
    if allow_missing_days:
        if (day_missing.any(axis=1) != day_missing.all(axis=1)).any():
            raise ValueError("missing values must cover whole days in every column")
    elif day_missing.any():
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

    Belgian day-ahead price plus the French day-ahead generation and load forecasts, the
    inputs of the benchmark (Lago et al., 2021). Days are local Brussels delivery days;
    15-minute values are averaged to hours and DST days, isolated missing hours and dropped
    days follow the rules of ``data/calendar.py``. Raw downloads are cached as parquet in
    ``cache_dir`` (git-ignored).
    """

    SERIES = {
        "Price": ("prices", "BE"),
        "Generation forecast FR": ("generation", "FR"),
        "Load forecast FR": ("load", "FR"),
    }

    def __init__(
        self,
        start: str = PHASE_B_DOWNLOAD[0],
        end: str = PHASE_B_DOWNLOAD[1],
        cache_dir: Path | str = CACHE_DIR,
        client=None,
    ):
        self.start, self.end = start, end
        self.columns = ["Price", *EXOGENOUS]
        self.cache_dir = Path(cache_dir)
        self.client = client
        self.report: dict = {}

    def raw(self, name: str) -> pd.Series:
        """UTC series of one column, from the cache or downloaded (end day included)."""
        kind, area = self.SERIES[name]
        path = self.cache_dir / f"{kind}_{area}_{self.start}_{self.end}.parquet"
        if path.exists():
            return pd.read_parquet(path).iloc[:, 0]
        if self.client is None:
            self.client = EntsoeClient()
        end = pd.Timestamp(self.end) + pd.Timedelta(days=1)
        s = self.client.query(kind, area, self.start, end)
        path.parent.mkdir(parents=True, exist_ok=True)
        s.to_frame().to_parquet(path)
        return s

    def load(self) -> pd.DataFrame:
        frame, self.report = standard_frame({c: self.raw(c) for c in self.columns})
        return validate_standard_frame(frame, allow_missing_days=True)


def train_test_split(df: pd.DataFrame, begin_test: str, end_test: str):
    """Split a standard frame into training history and test period (whole days)."""
    begin = pd.Timestamp(begin_test)
    end = pd.Timestamp(end_test) + pd.Timedelta(hours=23)
    return df.loc[: begin - pd.Timedelta(hours=1)], df.loc[begin:end]


# Test period of Lago et al. (2021) for BE: the last 2 x 364 days of the dataset.
BE_TEST_BEGIN, BE_TEST_END = PHASE_A_TEST
