"""AWS deployment: the S3 state of the daily run (scripts/aws_run.py) and the start of the
API on Lambda (be_power_forecast.cloud), with S3 mocked by moto."""

import importlib.util
import sys
from pathlib import Path

import boto3
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws

from be_power_forecast import cloud
from be_power_forecast.config import REPO_ROOT
from be_power_forecast.live_report import page_html

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("aws_run", ROOT / "scripts" / "aws_run.py")
aws_run = importlib.util.module_from_spec(spec)
spec.loader.exec_module(aws_run)

DATA, SITE = "be-power-forecast-data-test", "be-power-forecast-site-test"
LIVE_CSV = "results/forecasts/live/forecasts.csv"


@pytest.fixture
def s3(monkeypatch):
    for var in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
        monkeypatch.setenv(var, "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-1")
    with mock_aws():
        client = boto3.client("s3", region_name="eu-west-1")
        for name in (DATA, SITE):
            client.create_bucket(
                Bucket=name, CreateBucketConfiguration={"LocationConstraint": "eu-west-1"}
            )
        yield client


def put(s3, key, body, bucket=DATA):
    s3.put_object(Bucket=bucket, Key=key, Body=body.encode() if isinstance(body, str) else body)


def get(s3, key, bucket=DATA):
    return s3.get_object(Bucket=bucket, Key=key)["Body"].read().decode()


def objects(s3, bucket=DATA):
    return sorted(cloud.keys(s3, bucket, ""))


def seed(s3):
    put(s3, "cache/prices_BE_live.parquet", "old prices")
    put(s3, "cache/load_FR_live.parquet", "load")
    put(s3, "state/" + LIVE_CSV, "Date,h0\n2026-11-04,1\n")
    put(s3, "state/results/live/realised.csv", "Date,h0\n")
    put(s3, "state/live/README.md", "# Live\n\nold page\n")
    put(s3, "state/live/compare.png", b"\x89PNG old")


# A stand-in for scripts/live_forecast.py, run in the working directory as the real one:
# it extends the cache and the forecasts, rewrites the page and removes its chart.
FAKE_RUN = """
import os, pathlib, sys
root = pathlib.Path(os.environ["BE_REPO_ROOT"])
assert pathlib.Path.cwd() == root
assert (root / "data/raw/BE.csv").exists()  # the inputs of the image
(root / "data/cache/prices_BE_live.parquet").write_text("new prices")
with open(root / "results/forecasts/live/forecasts.csv", "a") as f:
    f.write("2026-11-05,2\\n")
(root / "live/README.md").write_text("# Live\\n\\n| Model | MAE |\\n|---|---|\\n| LEAR | 1.00 |\\n")
(root / "live/compare.png").unlink()
sys.exit(int(os.environ.get("FAKE_EXIT", "0")))
"""


class FakeLambda:
    def __init__(self):
        self.updates = []

    def get_function_configuration(self, FunctionName):
        return {"Environment": {"Variables": {"BE_DATA_BUCKET": DATA}}}

    def update_function_configuration(self, FunctionName, Environment):
        self.updates.append((FunctionName, Environment["Variables"]))


def run(s3, tmp_path, lam=None, **kwargs):
    command = [sys.executable, "-c", FAKE_RUN]
    return aws_run.run(DATA, tmp_path / "work", command, s3=s3, lam=lam, **kwargs)


def test_run_uploads_what_changed(s3, tmp_path):
    seed(s3)
    lam = FakeLambda()
    assert run(s3, tmp_path, lam, site_bucket=SITE, function="be-power-forecast-api") == 0
    assert get(s3, "cache/prices_BE_live.parquet") == "new prices"
    assert get(s3, "cache/load_FR_live.parquet") == "load"  # unchanged, kept
    assert get(s3, "state/" + LIVE_CSV).endswith("2026-11-05,2\n")
    assert "state/live/compare.png" not in objects(s3)  # removed by the run
    assert not any(k.startswith("state/data/") for k in objects(s3))  # inputs stay local
    page = get(s3, "index.html", SITE)
    assert page.startswith("<!doctype html>") and "<td>LEAR</td><td>1.00</td>" in page
    head = s3.head_object(Bucket=SITE, Key="index.html")
    assert head["ContentType"].startswith("text/html") and "max-age" in head["CacheControl"]
    assert objects(s3, SITE) == ["index.html"]  # no chart today
    # The forecasts changed: the API starts fresh execution environments.
    [(name, variables)] = lam.updates
    assert name == "be-power-forecast-api" and variables["BE_DATA_BUCKET"] == DATA
    assert "BE_STATE_VERSION" in variables


def test_only_changed_files_are_uploaded(s3, tmp_path):
    seed(s3)
    before = s3.head_object(Bucket=DATA, Key="cache/load_FR_live.parquet")["LastModified"]
    assert run(s3, tmp_path) == 0
    after = s3.head_object(Bucket=DATA, Key="cache/load_FR_live.parquet")["LastModified"]
    assert before == after


def test_failed_run_uploads_nothing(s3, tmp_path, monkeypatch):
    seed(s3)
    monkeypatch.setenv("FAKE_EXIT", "1")
    lam = FakeLambda()
    assert run(s3, tmp_path, lam, site_bucket=SITE, function="api") == 1
    assert get(s3, "cache/prices_BE_live.parquet") == "old prices"
    assert get(s3, "state/" + LIVE_CSV) == "Date,h0\n2026-11-04,1\n"
    assert "state/live/compare.png" in objects(s3)
    assert objects(s3, SITE) == [] and lam.updates == []


def test_empty_state_is_refused(s3, tmp_path):
    # Running on an empty state/ would replace the live history: seed it first.
    put(s3, "cache/prices_BE_live.parquet", "old prices")
    assert run(s3, tmp_path) == 2
    assert objects(s3) == ["cache/prices_BE_live.parquet"]


def test_upload_and_download_round_trip(s3, tmp_path):
    root = tmp_path / "root"
    for rel in ("live/README.md", "results/live/realised.csv", "data/cache/x.parquet"):
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(rel)
    sent = cloud.upload(s3, DATA, "state/", root, {}, paths=cloud.STATE_PATHS)
    assert sorted(sent) == ["live/README.md", "results/live/realised.csv"]
    back = cloud.download(s3, DATA, "state/", tmp_path / "back")
    assert back == {rel: cloud.md5(root / rel) for rel in sent}
    assert (tmp_path / "back" / "live/README.md").read_text() == "live/README.md"


def test_api_starts_on_the_forecasts_of_s3(s3, tmp_path, monkeypatch):
    # The live forecasts of S3 (one more day than the repository) and no ENTSO-E prices,
    # as on Lambda.
    live = pd.read_csv(REPO_ROOT / LIVE_CSV, index_col=0, parse_dates=True)
    day = live.index[-1] + pd.Timedelta(days=1)
    live.loc[day] = range(24)
    put(s3, "state/" + LIVE_CSV, live.to_csv())
    env = cloud.fetch_api_files(DATA, tmp_path / "api", s3=s3)
    # No DNN file in S3: the service keeps the one of the image.
    assert env == {"BE_LIVE_PATH": str(tmp_path / "api" / LIVE_CSV)}
    monkeypatch.setenv("BE_FORECAST_DIR", str(REPO_ROOT / "results/forecasts/phase_b"))
    monkeypatch.setenv("BE_PRICE_PATH", str(tmp_path / "no-prices.parquet"))
    for var, value in env.items():
        monkeypatch.setenv(var, value)
    from be_power_forecast.api.app import app

    with TestClient(app) as c:
        health = c.get("/health").json()
        assert health["status"] == "ok" and health["lear_forecasts"] and not health["prices"]
        assert health["last_day"] == str(day.date())
        answer = c.post("/forecast", json={"delivery_day": str(day.date())}).json()
        assert answer["model"] == "lear_ensemble" and answer["prices"] == list(range(24))
        # Without the prices there is no naive fallback: a day with no LEAR forecast is a 503.
        missing = pd.Timestamp("2026-11-03")
        if missing not in live.index:
            assert c.post("/forecast", json={"delivery_day": "2026-11-03"}).status_code == 503


def test_api_keeps_the_image_files_when_s3_fails(s3, tmp_path):
    assert cloud.fetch_api_files("no-such-bucket", tmp_path, s3=s3) == {}


def test_page_html():
    page = (ROOT / "live" / "README.md").read_text()
    out = page_html(page, aws_run.REPO_URL)
    assert out.count("<table>") == page.count("\n|---") and "<details>" in out
    assert '<img src="compare.png"' in out
    assert f"{aws_run.REPO_URL}/tree/main/src/be_power_forecast/sql" in out  # ../src link
    assert "<script" not in out
