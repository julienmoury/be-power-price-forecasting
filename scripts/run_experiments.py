"""Run every LEAR backtest used in the README and save forecasts to results/forecasts/.

Phase A: the paper's dataset (BE.csv), test 2015-01-04 to 2016-12-31, plus a diagnostic of
the gap to the published forecasts (exogenous lags of the pre-2024 library).
Phase B: the same 4-window protocol on the ENTSO-E standard frame built by
scripts/build_phase_b.py (data/cache/phase_b_FR.parquet), test 2019-01-01 to 2026-09-30;
forecasts go to results/forecasts/phase_b/.

Each experiment is skipped if its CSV already exists, so the script can be resumed; a CSV
that starts after the test period (phase B moved from 2019 to 2017 with the join of
BE.csv and ENTSO-E) is extended with the missing first days only.
With the ``mlops`` extra installed, every new backtest is logged as an MLflow run
(be_power_forecast.mlops.tracking); ``--track`` logs the backtests whose CSV already exists.
Usage: python scripts/run_experiments.py [--phase A|B] [--only NAME ...] [--n-jobs N] [--track]
"""

from __future__ import annotations

import argparse
import importlib.util
import time
from pathlib import Path

import pandas as pd

from be_power_forecast.backtest import daily_prices, lear_backtest
from be_power_forecast.config import CACHE_DIR, PHASE_B_TEST
from be_power_forecast.data.sources import (
    BE_TEST_BEGIN,
    BE_TEST_END,
    EpftoolboxZenodoSource,
    validate_standard_frame,
)
from be_power_forecast.evaluation.metrics import mae, rmse, smape
from be_power_forecast.mlops.tracking import log_backtest
from be_power_forecast.models.lear import DEFAULT_SPEC, FeatureSpec

TRACKING = importlib.util.find_spec("mlflow") is not None  # mlops extra installed

OUT = Path(__file__).resolve().parents[1] / "results" / "forecasts"

PAPER_WINDOWS = (56, 84, 1092, 1456)


# Exogenous lags D-1, D-2, D (epftoolbox before commit f234b08, June 2024) instead of
# D-1, D-7, D: checks whether the library version explains the gap to published forecasts.
LAGS_D2 = FeatureSpec(exogenous_lags=(1, 2, 0))


def experiments():
    for cw in PAPER_WINDOWS:
        yield f"lear_cw{cw}", cw, [], DEFAULT_SPEC
    for cw in (56, 84):
        yield f"lear_exoglags12_cw{cw}", cw, [], LAGS_D2


def track(phase, name, cw, drop, spec, fc, real, path, runtime=None) -> None:
    """Log one backtest (settings, accuracy on its forecast days, CSV path) to MLflow."""
    r = real.loc[fc.index]
    metrics = {"days": len(fc), "MAE": mae(r, fc), "RMSE": rmse(r, fc), "sMAPE": smape(r, fc)}
    if runtime is not None:
        metrics["runtime_s"] = runtime
    params = {
        "calibration_window": cw,
        "dropped_inputs": ",".join(drop) or "none",
        "exogenous_lags": ",".join(map(str, spec.exogenous_lags)),
        "test_begin": str(fc.index[0].date()),
        "test_end": str(fc.index[-1].date()),
    }
    log_backtest(name, phase, params, metrics, path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=["A", "B"], default="A")
    parser.add_argument("--only", nargs="*", help="experiment names to run")
    parser.add_argument("--n-jobs", type=int, default=None)
    parser.add_argument("--track", action="store_true", help="log existing CSVs to MLflow")
    args = parser.parse_args()
    if args.track and not TRACKING:
        parser.error("--track needs the mlops extra: pip install -e '.[mlops]'")

    if args.phase == "B":
        df = validate_standard_frame(
            pd.read_parquet(CACHE_DIR / "phase_b_FR.parquet"), allow_missing_days=True
        )
        out, (begin, end) = OUT / "phase_b", PHASE_B_TEST
        runs = [(f"lear_cw{cw}", cw, [], DEFAULT_SPEC) for cw in PAPER_WINDOWS]
    else:
        df = EpftoolboxZenodoSource("BE").load()
        out, (begin, end), runs = OUT, (BE_TEST_BEGIN, BE_TEST_END), experiments()
    real = daily_prices(df, begin, end)
    out.mkdir(parents=True, exist_ok=True)
    for name, cw, drop, spec in runs:
        path = out / f"{name}.csv"
        if args.only and name not in args.only:
            continue
        old = pd.read_csv(path, index_col=0, parse_dates=True) if path.exists() else None
        if old is not None and old.index[0] <= pd.Timestamp(begin):
            if args.track:
                track(args.phase, name, cw, drop, spec, old, real, path)
            continue
        stop = end if old is None else str((old.index[0] - pd.Timedelta(days=1)).date())
        start = time.time()
        fc = lear_backtest(df.drop(columns=drop), begin, stop, cw, spec, n_jobs=args.n_jobs)
        if old is not None:
            fc = pd.concat([fc, old])
        fc.to_csv(path, float_format="%.6f")
        runtime = time.time() - start
        print(f"{name}: {len(fc)} days in {runtime:.0f}s", flush=True)
        if TRACKING:
            track(args.phase, name, cw, drop, spec, fc, real, path, runtime)


if __name__ == "__main__":
    main()
