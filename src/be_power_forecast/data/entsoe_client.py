# Adapted from EnergieID/entsoe-py by EnergieID cvba-so and contributors (MIT) — changes:
# kept only the request parameters of documents A44, A65, A71 and A69 and the area codes
# of BE and FR; one simple retry with back-off instead of the decorators; requests split
# in calendar years (A44) or calendar months (A65, A71, A69, as entsoe-py's
# ``month_limited`` at commit 0cae400); token read from ENTSOE_API_KEY only.
"""Minimal client of the ENTSO-E Transparency Platform RESTful API."""

from __future__ import annotations

import os
import time

import pandas as pd
import requests

from be_power_forecast.data.entsoe_parser import parse_generation, parse_loads, parse_prices

ENDPOINT = "https://web-api.tp.entsoe.eu/api"
AREAS = {"BE": "10YBE----------2", "FR": "10YFR-RTE------C"}
# First delivery day cleared in 15-minute products by SDAC (Europe/Brussels), in UTC.
QUARTER_HOUR_GO_LIVE = pd.Timestamp("2025-10-01", tz="Europe/Brussels").tz_convert("UTC")

# kind -> (parameters builder, chunk frequency)
DOCUMENTS = {
    "prices": (
        lambda code: {
            "documentType": "A44",
            "in_Domain": code,
            "out_Domain": code,
            "contract_MarketAgreement.type": "A01",
        },
        "YS",
    ),
    "load": (
        lambda code: {
            "documentType": "A65",
            "processType": "A01",
            "outBiddingZone_Domain": code,
        },
        "MS",
    ),
    "generation": (
        lambda code: {"documentType": "A71", "processType": "A01", "in_Domain": code},
        "MS",
    ),
    "wind_solar": (
        lambda code: {"documentType": "A69", "processType": "A01", "in_Domain": code},
        "MS",
    ),
}


def _utc_str(ts: pd.Timestamp) -> str:
    return ts.tz_convert("UTC").strftime("%Y%m%d%H00")


def chunks(start: pd.Timestamp, end: pd.Timestamp, freq: str) -> list[tuple]:
    """Split ``[start, end)`` at calendar year (``YS``) or month (``MS``) boundaries."""
    cuts = pd.date_range(start, end, freq=freq, inclusive="neither")
    edges = [start, *cuts, end]
    return list(zip(edges[:-1], edges[1:], strict=True))


class EntsoeClient:
    """Download one series (``prices``, ``load``, ``generation``, ``wind_solar``) per call."""

    def __init__(self, api_key: str | None = None, session=None, retry_delay: float = 5.0):
        self.api_key = api_key or os.environ.get("ENTSOE_API_KEY")
        if not self.api_key:
            raise RuntimeError("set the ENTSOE_API_KEY environment variable")
        self.session = session or requests.Session()
        self.retry_delay = retry_delay

    def _request(self, params: dict, start: pd.Timestamp, end: pd.Timestamp) -> str | None:
        params = {
            **params,
            "securityToken": self.api_key,
            "periodStart": _utc_str(start),
            "periodEnd": _utc_str(end),
        }
        for attempt in range(2):
            try:
                response = self.session.get(ENDPOINT, params=params, timeout=60)
                if response.status_code < 500:
                    break
            except requests.ConnectionError:
                if attempt:
                    raise
            time.sleep(self.retry_delay * (attempt + 1))
        # The API answers "No matching data found" with 200 or 400 depending on the case.
        if "No matching data found" in response.text:
            return None
        response.raise_for_status()
        return response.text

    def query(self, kind: str, area: str, start, end) -> pd.Series:
        """Series ``kind`` for ``area`` on ``[start, end)``, UTC index, native resolution.

        Naive ``start``/``end`` are read as Europe/Brussels times.
        ``wind_solar`` is the sum of the solar, onshore and offshore wind forecasts.
        Prices are hourly before the 15-minute go-live and 15-minute after.
        """
        build, freq = DOCUMENTS[kind]
        start, end = _aware(start), _aware(end)
        parts = []
        for a, b in chunks(start, end, freq):
            text = self._request(build(AREAS[area]), a, b)
            if text is not None:
                parts.append(_parse(kind, text))
        if not parts:
            raise ValueError(f"no ENTSO-E data for {kind} {area} {start}-{end}")
        s = pd.concat(parts).sort_index()
        s = s[~s.index.duplicated(keep="first")]
        lo, hi = start.tz_convert("UTC"), end.tz_convert("UTC")
        return s[(s.index >= lo) & (s.index < hi)].rename(f"{kind} {area}")


def _aware(ts) -> pd.Timestamp:
    ts = pd.Timestamp(ts)
    return ts.tz_localize("Europe/Brussels") if ts.tzinfo is None else ts


def _parse(kind: str, text: str) -> pd.Series:
    if kind == "prices":
        # As entsoe-py: before the 15-minute go-live, every resolution (some hourly days
        # are published as PT15M) is reduced to hours by taking the first value.
        s = pd.concat([x for x in parse_prices(text).values() if len(x)]).sort_index()
        hourly = s[s.index < QUARTER_HOUR_GO_LIVE].resample("1h").first().dropna()
        return pd.concat([hourly, s[s.index >= QUARTER_HOUR_GO_LIVE]])
    if kind == "load":
        return parse_loads(text)
    frame = parse_generation(text)
    if kind == "generation":
        return frame["Actual Aggregated"]
    # A timestamp where one production type is missing stays missing (no partial sums).
    cols = [c for c in frame.columns if "consumption" not in c]
    return frame[cols].sum(axis=1, min_count=len(cols))
