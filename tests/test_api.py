import json

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from be_power_forecast.api.app import (
    DNNS,
    app,
    create_app,
    load_dnn_forecasts,
    load_lear_forecasts,
    load_prices,
)
from be_power_forecast.backtest import HOURS
from be_power_forecast.config import PAPER_WINDOWS, REPO_ROOT
from be_power_forecast.evaluation.metrics import naive_forecast, naive_source_day

# Synthetic data: prices 2018-12-20 .. 2019-01-31, LEAR forecasts 2019-01-01 .. 2019-01-31
# except 2019-01-15 (a day not forecast, as after a dropped day).
PRICE_DAYS = pd.date_range("2018-12-20", "2019-01-31")
FORECAST_DAYS = pd.date_range("2019-01-01", "2019-01-31").drop(pd.Timestamp("2019-01-15"))


@pytest.fixture
def data_dir(tmp_path):
    rng = np.random.default_rng(2026)
    for cw in PAPER_WINDOWS:
        fc = pd.DataFrame(rng.normal(60, 10, (len(FORECAST_DAYS), 24)), FORECAST_DAYS, HOURS)
        fc.index.name = "Date"
        fc.to_csv(tmp_path / f"lear_cw{cw}.csv", float_format="%.6f")
    hours = pd.date_range(PRICE_DAYS[0], periods=24 * len(PRICE_DAYS), freq="h", name="Date")
    frame = pd.DataFrame({"Price": rng.normal(60, 10, len(hours)), "Load forecast FR": 5e4}, hours)
    frame.to_parquet(tmp_path / "frame.parquet")
    return tmp_path


def client(lear_loader, price_loader):
    return TestClient(create_app(lear_loader, price_loader, first_day="2019-01-01"))


@pytest.fixture
def api(data_dir):
    with client(
        lambda: load_lear_forecasts(data_dir), lambda: load_prices(data_dir / "frame.parquet")
    ) as c:
        yield c


def post(c, day):
    return c.post("/forecast", json={"delivery_day": day})


def test_health(api):
    assert api.get("/health").json() == {
        "status": "ok",
        "lear_forecasts": True,
        "dnn_forecasts": False,
        "prices": True,
        "first_day": "2019-01-01",
        "last_day": "2019-02-01",  # day after the last known prices
    }


def test_lear_ensemble_is_mean_of_the_four_windows(api, data_dir):
    r = post(api, "2019-01-10")
    assert r.status_code == 200
    body = r.json()
    fcs = [pd.read_csv(data_dir / f"lear_cw{cw}.csv", index_col=0) for cw in PAPER_WINDOWS]
    expected = np.mean([f.loc["2019-01-10"].to_numpy() for f in fcs], axis=0)
    assert body["model"] == "lear_ensemble"
    assert np.allclose(body["prices"], expected) and len(body["prices"]) == 24
    assert body["inputs_until"] == "2019-01-09"


@pytest.mark.parametrize("day", ["2019-01-15", "2019-02-01"])  # Tuesday, Friday
def test_naive_fallback_when_no_lear_forecast(api, data_dir, day):
    body = post(api, day).json()
    prices = load_prices(data_dir / "frame.parquet")
    source = pd.Timestamp(day) - pd.Timedelta(days=1)
    assert body["model"] == "naive_fallback" and body["inputs_until"] == str(source.date())
    assert np.allclose(body["prices"], prices.loc[source].to_numpy())


def test_naive_fallback_when_forecasts_cannot_be_read(data_dir):
    def broken():
        raise OSError("forecast store unreachable")

    with client(broken, lambda: load_prices(data_dir / "frame.parquet")) as c:
        assert c.get("/health").json()["lear_forecasts"] is False
        body = post(c, "2019-01-14").json()  # Monday: copies the Monday before
    prices = load_prices(data_dir / "frame.parquet")
    assert body["model"] == "naive_fallback" and body["inputs_until"] == "2019-01-07"
    assert np.allclose(body["prices"], prices.loc["2019-01-07"].to_numpy())


def test_errors(api, data_dir):
    assert post(api, "2018-12-31").status_code == 404
    assert post(api, "2019-02-02").status_code == 404
    assert post(api, "2019-13-01").status_code == 422

    def broken():
        raise OSError

    with client(broken, broken) as c:
        assert c.get("/health").json()["status"] == "degraded"
        assert post(c, "2019-01-10").status_code == 503


def test_naive_source_day_matches_naive_forecast():
    days = pd.date_range("2019-01-01", "2019-01-31")
    prices = pd.DataFrame(np.arange(31 * 24, dtype=float).reshape(31, 24), days, HOURS)
    naive = naive_forecast(prices)
    for day in naive.index:
        assert (naive.loc[day] == prices.loc[naive_source_day(day)]).all()


def test_live_forecasts_are_served(data_dir):
    live = pd.DataFrame(
        [range(24)], pd.DatetimeIndex(["2019-02-01"], name="Date"), HOURS, dtype=float
    )
    live.to_csv(data_dir / "live.csv")
    with client(
        lambda: load_lear_forecasts(data_dir, data_dir / "live.csv"),
        lambda: load_prices(data_dir / "frame.parquet"),
    ) as c:
        body = post(c, "2019-02-01").json()
    assert body["model"] == "lear_ensemble"
    assert body["prices"] == [float(h) for h in range(24)]


def test_range_of_days(api):
    r = api.get("/forecasts", params={"start": "2019-01-14", "end": "2019-01-16"})
    assert r.status_code == 200
    body = r.json()
    assert [b["delivery_day"] for b in body] == ["2019-01-14", "2019-01-15", "2019-01-16"]
    assert [b["model"] for b in body] == ["lear_ensemble", "naive_fallback", "lear_ensemble"]
    for b in body:
        assert b == post(api, b["delivery_day"]).json()
    for start, end in [("2018-12-31", "2019-01-02"), ("2019-01-03", "2019-01-02")]:
        assert api.get("/forecasts", params={"start": start, "end": end}).status_code == 404


def test_openapi_contract_is_up_to_date():
    # docs/openapi.json is the contract with the consumers: python scripts/export_openapi.py
    assert json.loads((REPO_ROOT / "docs" / "openapi.json").read_text()) == app.openapi()


def test_dnn_ensemble_is_served_next_to_the_lear(data_dir):
    # DNN backtest for the first ten days, live DNN forecast for 2019-01-20.
    rng = np.random.default_rng(2026)
    days = FORECAST_DAYS[:10]
    fcs = {}
    for name in DNNS:
        fcs[name] = pd.DataFrame(rng.normal(60, 10, (len(days), 24)), days, HOURS)
        fcs[name].index.name = "Date"
        fcs[name].to_csv(data_dir / f"dnn_{name}.csv", float_format="%.6f")
    live = pd.DataFrame([np.arange(24.0)], pd.DatetimeIndex(["2019-01-20"], name="Date"), HOURS)
    live.to_csv(data_dir / "dnn_live.csv")
    app_ = create_app(
        lambda: load_lear_forecasts(data_dir),
        lambda: load_prices(data_dir / "frame.parquet"),
        first_day="2019-01-01",
        dnn_loader=lambda: load_dnn_forecasts(data_dir, data_dir / "dnn_live.csv"),
    )
    with TestClient(app_) as c:
        assert c.get("/health").json()["dnn_forecasts"] is True
        body = post(c, "2019-01-03").json()
        expected = np.mean(
            [pd.read_csv(data_dir / f"dnn_{n}.csv", index_col=0).loc["2019-01-03"] for n in DNNS],
            axis=0,
        )
        assert body["model"] == "lear_ensemble"
        np.testing.assert_allclose(body["dnn_prices"], expected)
        assert post(c, "2019-01-20").json()["dnn_prices"] == list(range(24))
        assert post(c, "2019-01-25").json()["dnn_prices"] is None
