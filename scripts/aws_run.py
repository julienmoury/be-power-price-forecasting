"""Run the daily live forecast on AWS: S3 in, scripts/live_forecast.py unchanged, S3 out.

The ECS Fargate task of infra/ (two EventBridge schedules, 17:30 and 20:30 UTC, as the
former GitHub Actions crons) runs this script in the image of the project. It

1. downloads ``cache/`` (ENTSO-E and SMARD downloads) and ``state/`` (the live forecasts,
   realised prices, DNN training records and page, under their repository paths) of the
   private data bucket ``BE_DATA_BUCKET`` into a working directory, with the inputs of the
   image (``data/raw``: BE.csv and the DNN hyperparameters);
2. runs ``scripts/live_forecast.py`` with ``BE_REPO_ROOT`` set to that directory, so the
   computation is the one of the repository, file for file;
3. uploads the files that changed (nothing when the forecast fails), publishes the live
   page as ``index.html`` with its chart to the private bucket behind CloudFront
   (``BE_SITE_BUCKET``), and makes the API on Lambda (``BE_API_FUNCTION``) reload the new
   forecasts on its next request.

``ENTSOE_API_KEY`` comes from the environment (SSM Parameter Store, injected by ECS). The
ENTSO-E data stay in the private bucket: only the page (our forecasts and the SMARD prices,
CC BY 4.0) is published. The same script runs the fallback workflow of GitHub Actions
(.github/workflows/live.yml).
Usage: python scripts/aws_run.py [--day YYYY-MM-DD] [--page-only] [--allow-empty-state]
"""

from __future__ import annotations

import argparse
import datetime as dt
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from be_power_forecast import cloud
from be_power_forecast.live_report import page_html

ROOT = Path(__file__).resolve().parents[1]  # /app in the image, the checkout otherwise
LIVE_SCRIPT = Path(__file__).resolve().parent / "live_forecast.py"
REPO_URL = "https://github.com/julienmoury/be-power-price-forecasting"
PAGE_CACHE = "public, max-age=300"  # CloudFront and browsers pick the new page within 5 min

log = logging.getLogger("aws_run")


def prepare(work: Path) -> None:
    """The inputs of the computation that are part of the code (data/raw of the image)."""
    raw = ROOT / "data" / "raw"
    if raw.exists() and raw.resolve() != (work / "data" / "raw").resolve():
        shutil.copytree(raw, work / "data" / "raw", dirs_exist_ok=True)


def publish_page(s3, bucket: str, page: Path) -> None:
    """``live/README.md`` as ``index.html``, with ``compare.png`` when the page has one."""
    markdown = (page / "README.md").read_text()
    s3.put_object(
        Bucket=bucket,
        Key="index.html",
        Body=page_html(markdown, REPO_URL).encode(),
        ContentType="text/html; charset=utf-8",
        CacheControl=PAGE_CACHE,
    )
    chart = page / "compare.png"
    if chart.exists():
        s3.put_object(
            Bucket=bucket,
            Key="compare.png",
            Body=chart.read_bytes(),
            ContentType="image/png",
            CacheControl=PAGE_CACHE,
        )
    else:
        s3.delete_object(Bucket=bucket, Key="compare.png")


def refresh_api(lam, function: str) -> None:
    """New execution environments for the API, which reads the forecasts when it starts:
    a configuration change makes Lambda start fresh ones. A failure (e.g. a deployment in
    progress) is logged, not raised: the forecasts are already stored."""
    from botocore.exceptions import BotoCoreError, ClientError

    try:
        config = lam.get_function_configuration(FunctionName=function)
        variables = config.get("Environment", {}).get("Variables", {})
        variables["BE_STATE_VERSION"] = dt.datetime.now(dt.timezone.utc).isoformat()
        lam.update_function_configuration(
            FunctionName=function, Environment={"Variables": variables}
        )
    except (BotoCoreError, ClientError) as err:
        log.warning("API not refreshed: %s", err)


def run(
    bucket: str,
    work: Path,
    command: list[str],
    site_bucket: str | None = None,
    function: str | None = None,
    allow_empty_state: bool = False,
    s3=None,
    lam=None,
) -> int:
    """One live run in ``work``; returns the exit code of the computation."""
    s3 = s3 or cloud.client("s3")
    work.mkdir(parents=True, exist_ok=True)
    prepare(work)
    cache = cloud.download(s3, bucket, cloud.CACHE_PREFIX, work / "data" / "cache")
    state = cloud.download(s3, bucket, cloud.STATE_PREFIX, work)
    log.info("downloaded %d cache and %d state files", len(cache), len(state))
    if not cloud.files_inside(state, cloud.STATE_PATHS) and not allow_empty_state:
        # Starting from nothing would replace the live history: seed state/ first.
        log.error("s3://%s/%s is empty: seed it first (docs/aws.md)", bucket, cloud.STATE_PREFIX)
        return 2
    env = {**os.environ, "BE_REPO_ROOT": str(work)}
    code = subprocess.run(command, cwd=work, env=env).returncode
    if code:
        log.error("live forecast failed (exit code %d): nothing uploaded", code)
        return code
    root = work / "data" / "cache"
    new_cache = cloud.upload(s3, bucket, cloud.CACHE_PREFIX, root, cache)
    new_state = cloud.upload(
        s3, bucket, cloud.STATE_PREFIX, work, state, paths=cloud.STATE_PATHS, delete=True
    )
    log.info("uploaded %d cache files; state: %s", len(new_cache), ", ".join(new_state) or "-")
    if site_bucket:
        publish_page(s3, site_bucket, work / "live")
        log.info("page published to s3://%s/index.html", site_bucket)
    if function and any(r in new_state for r in cloud.API_FILES.values()):
        refresh_api(lam or cloud.client("lambda"), function)
        log.info("API %s refreshed", function)
    return 0


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--day", help="delivery day (default: tomorrow, Brussels time)")
    parser.add_argument("--page-only", action="store_true", help="only refresh the page")
    parser.add_argument("--allow-empty-state", action="store_true")
    args = parser.parse_args()
    command = [sys.executable, str(LIVE_SCRIPT)]
    command += ["--day", args.day] if args.day else []
    command += ["--page-only"] if args.page_only else []
    work = Path(os.environ.get("BE_WORK_DIR") or tempfile.mkdtemp(prefix="be-live-"))
    sys.exit(
        run(
            os.environ["BE_DATA_BUCKET"],
            work,
            command,
            site_bucket=os.environ.get("BE_SITE_BUCKET"),
            function=os.environ.get("BE_API_FUNCTION"),
            allow_empty_state=args.allow_empty_state,
        )
    )


if __name__ == "__main__":
    main()
