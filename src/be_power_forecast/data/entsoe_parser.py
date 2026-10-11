# Adapted from EnergieID/entsoe-py by EnergieID cvba-so and contributors (MIT) — changes:
# xml.etree.ElementTree instead of BeautifulSoup (namespace-agnostic tag matching); kept
# only the parsers of day-ahead prices (A44), load forecasts (A65) and generation
# forecasts (A71); PT15M/PT30M/PT60M resolutions only; series
# returned as UTC-indexed float pandas objects; no netting options or per-plant parsing.
"""Parse ENTSO-E Transparency Platform XML documents into UTC-indexed series."""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pandas as pd

RESOLUTIONS = {"PT15M": "15min", "PT30M": "30min", "PT60M": "60min"}


_EMPTY = pd.Series(dtype=float, index=pd.DatetimeIndex([], tz="UTC"))


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _find(element: ET.Element, name: str) -> ET.Element | None:
    """First descendant whose tag (without namespace) is ``name``."""
    return next((e for e in element.iter() if _local(e.tag) == name), None)


def _findall(element: ET.Element, name: str) -> list[ET.Element]:
    return [e for e in element.iter() if _local(e.tag) == name]


def _text(element: ET.Element, name: str) -> str:
    found = _find(element, name)
    if found is None:
        raise ValueError(f"missing element <{name}>")
    return found.text.strip()


def _extract_timeseries(xml_text: str) -> list[ET.Element]:
    if not xml_text:
        return []
    return _findall(ET.fromstring(xml_text), "TimeSeries")


def _resolution_to_timedelta(res_text: str) -> str:
    if res_text not in RESOLUTIONS:
        raise NotImplementedError(f"unsupported ENTSO-E resolution {res_text!r}")
    return RESOLUTIONS[res_text]


def _parse_timeseries_generic(timeseries: ET.Element, label: str = "quantity") -> dict:
    """Values of one ``TimeSeries``, as one UTC-indexed series per resolution.

    Curve type A03 ("variable sized block") omits the positions whose value repeats the
    previous one: the series is reindexed on the full period and forward-filled.
    """
    series: dict[str, list[pd.Series]] = {freq: [] for freq in RESOLUTIONS.values()}
    curve_type = _text(timeseries, "curveType")
    for period in _findall(timeseries, "Period"):
        start = pd.Timestamp(_text(period, "start"))
        end = pd.Timestamp(_text(period, "end"))
        freq = _resolution_to_timedelta(_text(period, "resolution"))
        delta = pd.Timedelta(freq)
        data = {
            start + (int(_text(p, "position").replace(",", "")) - 1) * delta: float(
                _text(p, label).replace(",", "")
            )
            for p in _findall(period, "Point")
        }
        s = pd.Series(data, dtype=float).sort_index()
        if curve_type == "A03":
            s = s.reindex(pd.date_range(start, end - delta, freq=freq)).ffill()
        series[freq].append(s)
    return {
        freq: pd.concat(parts).sort_index() if parts else None for freq, parts in series.items()
    }


def _merge(parts: dict) -> pd.Series:
    return pd.concat([s for s in parts.values() if s is not None]).sort_index()


def parse_prices(xml_text: str) -> dict[str, pd.Series]:
    """Day-ahead prices (A44, EUR/MWh) split by resolution (``15min``, ``30min``, ``60min``)."""
    series: dict[str, list[pd.Series]] = {freq: [] for freq in RESOLUTIONS.values()}
    for ts in _extract_timeseries(xml_text):
        for freq, s in _parse_timeseries_generic(ts, "price.amount").items():
            if s is not None:
                series[freq].append(s)
    return {
        freq: pd.concat(parts).sort_index() if parts else _EMPTY.copy()
        for freq, parts in series.items()
    }


def parse_loads(xml_text: str) -> pd.Series:
    """Day-ahead total load forecast (A65, process type A01), MW."""
    parts = [_merge(_parse_timeseries_generic(ts)) for ts in _extract_timeseries(xml_text)]
    return pd.concat(parts).sort_index().rename("Forecasted Load")


def parse_generation(xml_text: str) -> pd.DataFrame:
    """Day-ahead generation forecasts (A71), MW.

    One column per production type code when the document has one, else ``Actual
    Aggregated``; series measured as consumption (``outBiddingZone_Domain``) get the suffix
    `` (consumption)``. Duplicated timestamps keep the first value, as in entsoe-py.
    """
    columns: dict[str, list[pd.Series]] = {}
    for ts in _extract_timeseries(xml_text):
        psr = _find(ts, "psrType")
        name = psr.text.strip() if psr is not None else "Actual Aggregated"
        if _find(ts, "outBiddingZone_Domain.mRID") is not None:
            name += " (consumption)"
        columns.setdefault(name, []).append(_merge(_parse_timeseries_generic(ts)))
    frames = {}
    for name, parts in columns.items():
        s = pd.concat(parts).sort_index()
        frames[name] = s[~s.index.duplicated(keep="first")]
    return pd.DataFrame(frames).sort_index()
