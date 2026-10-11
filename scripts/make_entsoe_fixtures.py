"""Write the synthetic ENTSO-E XML fixtures of tests/fixtures/entsoe/.

The documents follow the ENTSO-E schema as read by entsoe-py (TimeSeries, Period,
timeInterval, resolution, Point/position, value tag) but every value is synthetic, drawn
from a seeded generator: no real ENTSO-E data is committed.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "entsoe"
BE, FR = "10YBE----------2", "10YFR-RTE------C"
PUB_NS = "urn:iec62325.351:tc57wg16:451-3:publicationdocument:7:3"
GL_NS = "urn:iec62325.351:tc57wg16:451-6:generationloaddocument:3:0"
RNG = np.random.default_rng(2026)


def utc(day: str) -> pd.Timestamp:
    return pd.Timestamp(day, tz="Europe/Brussels").tz_convert("UTC")


def delivery_day(day: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    """UTC bounds of a local delivery day (23 or 25 hours at DST changes)."""
    return utc(day), utc(str((pd.Timestamp(day) + pd.Timedelta(days=1)).date()))


def z(ts: pd.Timestamp) -> str:
    return ts.strftime("%Y-%m-%dT%H:%MZ")


def period(start, end, resolution, values, tag, skip=()):
    points = "".join(
        f"<Point><position>{i + 1}</position><{tag}>{v:.2f}</{tag}></Point>"
        for i, v in enumerate(values)
        if i not in skip
    )
    return (
        f"<Period><timeInterval><start>{z(start)}</start><end>{z(end)}</end></timeInterval>"
        f"<resolution>{resolution}</resolution>{points}</Period>"
    )


def n_steps(start, end, resolution) -> int:
    return int((end - start) / pd.Timedelta(minutes=int(resolution[2:-1])))


def price_doc(days, resolution, curve, skip=()):
    series = []
    for k, day in enumerate(days):
        start, end = delivery_day(day)
        n = n_steps(start, end, resolution)
        values = 60 + 25 * np.sin(np.arange(n) * 2 * np.pi / n) + RNG.normal(0, 8, n)
        values[n // 2] = -12.5  # one negative price per day
        if skip:  # A03: an omitted position repeats the previous value
            for i in skip:
                values[i] = values[i - 1]
        series.append(
            f"<TimeSeries><mRID>{k + 1}</mRID><businessType>A62</businessType>"
            f'<in_Domain.mRID codingScheme="A01">{BE}</in_Domain.mRID>'
            f'<out_Domain.mRID codingScheme="A01">{BE}</out_Domain.mRID>'
            "<currency_Unit.name>EUR</currency_Unit.name>"
            "<price_Measure_Unit.name>MWH</price_Measure_Unit.name>"
            f"<curveType>{curve}</curveType>"
            f"{period(start, end, resolution, values, 'price.amount', skip)}</TimeSeries>"
        )
    return (
        f'<?xml version="1.0" encoding="utf-8"?>\n<Publication_MarketDocument xmlns="{PUB_NS}">'
        f"<mRID>synthetic</mRID><type>A44</type>{''.join(series)}</Publication_MarketDocument>\n"
    )


def gl_doc(doc_type, process, days, resolution, area, domain_tag, level):
    series = []
    for day in days:
        start, end = delivery_day(day)
        n = n_steps(start, end, resolution)
        values = level * (1 + 0.15 * np.sin(np.arange(n) * 2 * np.pi / n))
        values = np.round(values + RNG.normal(0, level * 0.02, n))
        series.append(
            f"<TimeSeries><mRID>{len(series) + 1}</mRID><businessType>A01</businessType>"
            "<objectAggregation>A01</objectAggregation>"
            f'<{domain_tag} codingScheme="A01">{area}</{domain_tag}>'
            "<quantity_Measure_Unit.name>MAW</quantity_Measure_Unit.name>"
            "<curveType>A01</curveType>"
            f"{period(start, end, resolution, values, 'quantity')}</TimeSeries>"
        )
    return (
        f'<?xml version="1.0" encoding="utf-8"?>\n<GL_MarketDocument xmlns="{GL_NS}">'
        f"<mRID>synthetic</mRID><type>{doc_type}</type><process.processType>{process}"
        f"</process.processType>{''.join(series)}</GL_MarketDocument>\n"
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    two_days = ["2025-01-14", "2025-01-15"]
    files = {
        "prices_A44_hourly.xml": price_doc(two_days, "PT60M", "A01"),
        "prices_A44_quarter_hour.xml": price_doc(
            ["2025-10-02"], "PT15M", "A03", skip=(5, 6, 30, 77, 95)
        ),
        "load_A65_dst_spring.xml": gl_doc(
            "A65", "A01", ["2025-03-30"], "PT60M", FR, "outBiddingZone_Domain.mRID", 55000
        ),
        "load_A65_dst_autumn.xml": gl_doc(
            "A65", "A01", ["2025-10-26"], "PT60M", FR, "outBiddingZone_Domain.mRID", 50000
        ),
        "generation_A71.xml": gl_doc(
            "A71", "A01", two_days, "PT60M", FR, "inBiddingZone_Domain.mRID", 60000
        ),
    }
    for name, text in files.items():
        (OUT / name).write_text(text)


if __name__ == "__main__":
    main()
