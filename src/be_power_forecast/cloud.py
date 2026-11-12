"""State of the AWS deployment in S3 (docs/aws.md), and the start of the API on Lambda.

The private data bucket holds

* ``cache/``: the ENTSO-E and SMARD downloads, i.e. ``data/cache/`` of a checkout. The
  ENTSO-E prices are never made public (re-use terms): this bucket is private;
* ``state/``: the files the daily live run reads and writes, under their paths in the
  repository (``STATE_PATHS``).

The daily run (``scripts/aws_run.py``, an ECS Fargate task) downloads both into a working
directory, runs ``scripts/live_forecast.py`` unchanged on it and uploads what changed. On
Lambda, ``python -m be_power_forecast.cloud`` copies the live forecast files of ``state/``
to ``/tmp``, points the ``BE_*_LIVE_PATH`` variables at them and starts the
unchanged forecast service (``api/app.py``) behind the AWS Lambda Web Adapter. The phase B
backtest forecasts are those of the image; the ENTSO-E prices (naive fallback) are not given
to Lambda, so the service runs as it does locally when the price file is missing.
"""

from __future__ import annotations

import hashlib
import logging
import mimetypes
import os
from pathlib import Path

log = logging.getLogger(__name__)

CACHE_PREFIX = "cache/"
STATE_PREFIX = "state/"
# Written by scripts/live_forecast.py, under their paths in the repository.
STATE_PATHS = ("results/forecasts/live", "results/dnn/live", "results/live", "live")
# The files of state/ the API reads, by the environment variable of api/app.py.
API_FILES = {
    "BE_LIVE_PATH": "results/forecasts/live/forecasts.csv",
    "BE_DNN_LIVE_PATH": "results/forecasts/live/dnn_forecasts.csv",
    "BE_LGBM_LIVE_PATH": "results/forecasts/live/lgbm_forecasts.csv",
}


def client(service: str):
    import boto3

    return boto3.client(service)


def md5(path: Path) -> str:
    return hashlib.md5(Path(path).read_bytes(), usedforsecurity=False).hexdigest()


def keys(s3, bucket: str, prefix: str) -> list[str]:
    pages = s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix)
    return [o["Key"] for page in pages for o in page.get("Contents", [])]


def download(s3, bucket: str, prefix: str, dest: Path) -> dict[str, str]:
    """Copy every object under ``prefix`` to ``dest`` (same relative paths); returns the MD5
    of each file by relative path, to upload only what changed."""
    out = {}
    for key in keys(s3, bucket, prefix):
        rel = key[len(prefix) :]
        if not rel or rel.endswith("/"):
            continue
        path = Path(dest) / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        s3.download_file(bucket, key, str(path))
        out[rel] = md5(path)
    return out


def files(root: Path, paths=None) -> dict[str, Path]:
    """Files under ``root`` (only under its sub-paths ``paths`` if given), by relative path."""
    root = Path(root)
    tops = [root / p for p in paths] if paths is not None else [root]
    found = (f for top in tops if top.exists() for f in sorted(top.rglob("*")) if f.is_file())
    return {f.relative_to(root).as_posix(): f for f in found}


def upload(
    s3,
    bucket: str,
    prefix: str,
    root: Path,
    before: dict[str, str],
    paths=None,
    delete: bool = False,
) -> list[str]:
    """Upload the files of ``root`` that are new or changed since ``before`` (see
    ``download``); with ``delete``, remove the objects whose file is gone. Returns the
    relative paths uploaded or removed."""
    now = files(root, paths)
    changed = []
    for rel, path in now.items():
        if before.get(rel) != md5(path):
            kind = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            s3.upload_file(str(path), bucket, prefix + rel, ExtraArgs={"ContentType": kind})
            changed.append(rel)
    if delete:
        inside = files_inside(before, paths)
        for rel in sorted(set(inside) - set(now)):
            s3.delete_object(Bucket=bucket, Key=prefix + rel)
            changed.append(rel)
    return changed


def files_inside(listing: dict[str, str], paths=None) -> list[str]:
    if paths is None:
        return list(listing)
    return [r for r in listing if any(r == p or r.startswith(p.rstrip("/") + "/") for p in paths)]


def fetch_api_files(bucket: str, dest: Path, s3=None) -> dict[str, str]:
    """Copy the live forecast files of ``state/`` to ``dest``; returns the ``BE_*``
    variables pointing at them. A file that cannot be fetched keeps the path of the image
    (the live forecasts as of its build), so that the service still starts."""
    from botocore.exceptions import BotoCoreError, ClientError

    s3 = s3 or client("s3")
    env = {}
    for var, rel in API_FILES.items():
        path = Path(dest) / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            s3.download_file(bucket, STATE_PREFIX + rel, str(path))
        except (BotoCoreError, ClientError) as err:
            log.warning("%s: kept the copy of the image (%s)", rel, err)
            continue
        env[var] = str(path)
    return env


def serve() -> None:
    """Start the forecast service on ``PORT`` (8080, the port of the Lambda Web Adapter),
    with the live forecasts of ``BE_DATA_BUCKET`` when it is set."""
    logging.basicConfig(level=logging.INFO)
    bucket = os.environ.get("BE_DATA_BUCKET")
    if bucket:
        os.environ.update(fetch_api_files(bucket, Path(os.environ.get("BE_API_DIR", "/tmp/api"))))
    port = os.environ.get("PORT", "8080")
    app = "be_power_forecast.api.app:app"
    os.execvp("uvicorn", ["uvicorn", app, "--host", "0.0.0.0", "--port", port])


if __name__ == "__main__":
    serve()
