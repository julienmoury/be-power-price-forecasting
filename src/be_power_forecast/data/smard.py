"""Belgian day-ahead prices from SMARD.de (Bundesnetzagentur), published under CC BY 4.0.

Used only to show realised prices next to the live forecasts (the ENTSO-E prices are not on
its free re-use list); the models keep the ENTSO-E inputs of the
backtests. SMARD receives the prices from ENTSO-E: on September 2026 both are equal at every
hour. Attribution required: "Bundesnetzagentur | SMARD.de" (www.smard.de/en/datennutzung).
"""

from __future__ import annotations

import json
import urllib.request

import pandas as pd

ATTRIBUTION = "Bundesnetzagentur | SMARD.de, CC BY 4.0"
URL = "https://www.smard.de/app/chart_data/4996/DE/{name}.json"  # filter 4996: price BE


def _get(name: str) -> dict:
    with urllib.request.urlopen(URL.format(name=name), timeout=30) as r:
        return json.load(r)


def smard_prices(start: pd.Timestamp, end: pd.Timestamp, get=_get) -> pd.Series:
    """UTC-indexed quarter-hour Belgian prices (EUR/MWh) from ``start`` to ``end`` (UTC).

    SMARD serves weekly files listed in an index; ``get`` is injected in tests.
    """
    weeks = get("index_quarterhour")["timestamps"]
    lo, hi = start.value // 10**6, end.value // 10**6
    week_ms = 7 * 24 * 3600 * 1000
    rows = []
    for w in weeks:
        if lo - week_ms < w <= hi:
            rows += get(f"4996_DE_quarterhour_{w}")["series"]
    s = pd.Series(
        {pd.Timestamp(t, unit="ms", tz="UTC"): v for t, v in rows if v is not None}, dtype=float
    ).sort_index()
    return s[(s.index >= start) & (s.index < end)]
