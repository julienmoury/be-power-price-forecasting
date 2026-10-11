from pathlib import Path

import pandas as pd
import pytest

from be_power_forecast.data.entsoe_client import EntsoeClient, chunks
from be_power_forecast.data.entsoe_parser import parse_generation, parse_loads, parse_prices

FIXTURES = Path(__file__).parent / "fixtures" / "entsoe"
REFERENCE = Path(__file__).parent / "reference" / "entsoe_parsed_reference.csv"


def parsed_long(name: str) -> pd.DataFrame:
    text = (FIXTURES / name).read_text()
    if name.startswith("prices"):
        frame = pd.DataFrame({k: v for k, v in parse_prices(text).items() if len(v)})
    elif name.startswith("load"):
        frame = parse_loads(text).to_frame()
    else:
        frame = parse_generation(text)
    out = frame.stack().rename("value").reset_index()
    out.columns = ["timestamp", "series", "value"]
    out["timestamp"] = out["timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return out


@pytest.mark.parametrize("name", sorted(p.name for p in FIXTURES.glob("*.xml")))
def test_parser_matches_original_entsoe_py(name):
    ref = pd.read_csv(REFERENCE, float_precision="round_trip")
    ref = ref[ref["file"] == name].drop(columns="file")
    ours = parsed_long(name)
    key = ["series", "timestamp"]
    ref = ref.sort_values(key).reset_index(drop=True)
    ours = ours.sort_values(key).reset_index(drop=True)
    assert len(ours) == len(ref) > 0
    pd.testing.assert_frame_equal(ours[key], ref[key])
    assert (ours["value"].to_numpy() == ref["value"].to_numpy()).all()  # exact


def test_a03_curve_repeats_omitted_positions():
    prices = parse_prices((FIXTURES / "prices_A44_quarter_hour.xml").read_text())["15min"]
    assert len(prices) == 96 and not prices.isna().any()
    assert prices.iloc[5] == prices.iloc[4] == prices.iloc[6]  # positions 6 and 7 omitted
    assert prices.index[0] == pd.Timestamp("2025-10-01 22:00", tz="UTC")


class FakeResponse:
    def __init__(self, text, status_code=200):
        self.text, self.status_code = text, status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


class FakeSession:
    def __init__(self, text):
        self.text, self.calls = text, []

    def get(self, url, params, timeout):
        self.calls.append((url, dict(params)))
        return FakeResponse(self.text)


def test_client_builds_entsoe_requests_without_network():
    session = FakeSession((FIXTURES / "prices_A44_hourly.xml").read_text())
    client = EntsoeClient(api_key="dummy", session=session)
    s = client.query("prices", "BE", "2024-12-15", "2025-02-01")
    url, params = session.calls[0]
    assert url == "https://web-api.tp.entsoe.eu/api"
    assert params == {
        "documentType": "A44",
        "in_Domain": "10YBE----------2",
        "out_Domain": "10YBE----------2",
        "contract_MarketAgreement.type": "A01",
        "securityToken": "dummy",
        "periodStart": "202412142300",  # local midnight, written in UTC
        "periodEnd": "202412312300",
    }
    assert len(session.calls) == 2  # split at the calendar year
    assert len(s) == 48 and s.index.tz is not None


@pytest.mark.parametrize(
    "kind, area, expected",
    [
        ("load", "FR", {"documentType": "A65", "processType": "A01",
                        "outBiddingZone_Domain": "10YFR-RTE------C"}),
        ("generation", "FR", {"documentType": "A71", "processType": "A01",
                              "in_Domain": "10YFR-RTE------C"}),
    ],
)  # fmt: skip
def test_client_forecast_parameters_and_monthly_chunks(kind, area, expected):
    fixture = {"load": "load_A65_dst_spring.xml", "generation": "generation_A71.xml"}
    text = (FIXTURES / fixture[kind]).read_text()
    session = FakeSession(text)
    EntsoeClient(api_key="dummy", session=session).query(kind, area, "2025-01-01", "2025-04-01")
    assert len(session.calls) == 3
    params = session.calls[0][1]
    assert {k: params[k] for k in expected} == expected


def test_client_requires_api_key(monkeypatch):
    monkeypatch.delenv("ENTSOE_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ENTSOE_API_KEY"):
        EntsoeClient()


def test_no_matching_data_raises_clear_error():
    session = FakeSession("<Acknowledgement_MarketDocument>No matching data found")
    session.get = lambda url, params, timeout: FakeResponse(session.text, 400)
    with pytest.raises(ValueError, match="no ENTSO-E data"):
        EntsoeClient(api_key="k", session=session).query("load", "BE", "2025-01-01", "2025-01-02")


def test_chunks_cover_the_interval_at_calendar_boundaries():
    start = pd.Timestamp("2015-01-01", tz="Europe/Brussels")
    end = pd.Timestamp("2017-03-15", tz="Europe/Brussels")
    parts = chunks(start, end, "YS")
    assert parts[0][0] == start and parts[-1][1] == end and len(parts) == 3
    assert all(a[1] == b[0] for a, b in zip(parts[:-1], parts[1:], strict=True))
