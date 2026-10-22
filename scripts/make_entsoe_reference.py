"""Parse the XML fixtures with the ORIGINAL client's parsers (reference for the adapted ones).

Not run in CI. Run once in a throw-away virtual environment:

    # the original ENTSO-E client, checked out at commit 0cae400 in ./entsoe-py
    python -m venv /tmp/entsoe-ref && /tmp/entsoe-ref/bin/pip install ./entsoe-py
    /tmp/entsoe-ref/bin/python scripts/make_entsoe_reference.py

Writes tests/reference/entsoe_parsed_reference.csv in long format
(file, series, timestamp in UTC, value).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from entsoe.parsers import parse_generation, parse_loads, parse_prices

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "entsoe"
OUT = ROOT / "tests" / "reference" / "entsoe_parsed_reference.csv"


def long(file: str, frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.stack().rename("value").reset_index()
    out.columns = ["timestamp", "series", "value"]
    out.insert(0, "file", file)
    return out


def main() -> None:
    rows = []
    for path in sorted(FIXTURES.glob("*.xml")):
        text = path.read_text()
        if path.name.startswith("prices"):
            parsed = parse_prices(text)
            frame = pd.DataFrame({k: v for k, v in parsed.items() if len(v)})
        elif path.name.startswith("load"):
            frame = parse_loads(text, process_type="A01")
        else:
            frame = parse_generation(text, nett=False)
            if isinstance(frame, pd.Series):
                frame = frame.to_frame()
        rows.append(long(path.name, frame))
    out = pd.concat(rows)
    out["timestamp"] = pd.to_datetime(out["timestamp"], utc=True).dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    out.to_csv(OUT, index=False)  # repr floats: exact round trip
    print(f"{len(out)} values written to {OUT}")


if __name__ == "__main__":
    main()
