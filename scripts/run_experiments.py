"""Run every backtest of the README (LEAR, LightGBM) and save forecasts to results/forecasts/.

Each experiment is skipped if its CSV already exists, so the script can be resumed.
Usage: python scripts/run_experiments.py [--only NAME ...] [--n-jobs N]
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from be_power_forecast.backtest import lear_backtest
from be_power_forecast.data.sources import BE_TEST_BEGIN, BE_TEST_END, EpftoolboxZenodoSource
from be_power_forecast.models.challenger import lgbm_backtest
from be_power_forecast.models.lear import DEFAULT_SPEC, FeatureSpec

OUT = Path(__file__).resolve().parents[1] / "results" / "forecasts"

PAPER_WINDOWS = (56, 84, 1092, 1456)
EXTRA_WINDOWS = (28, 182, 364, 728)

# name -> columns dropped from the standard frame
ABLATIONS = {
    "no_exog": ["Generation forecast FR", "Load forecast FR"],
    "no_load_fr": ["Load forecast FR"],
    "no_gen_fr": ["Generation forecast FR"],
}


# Exogenous lags D-1, D-2, D (epftoolbox before commit f234b08, June 2024) instead of
# D-1, D-7, D: checks whether the library version explains the gap to published forecasts.
LAGS_D2 = FeatureSpec(exogenous_lags=(1, 2, 0))


def experiments():
    for cw in PAPER_WINDOWS:
        yield f"lear_cw{cw}", cw, [], DEFAULT_SPEC
    for name, drop in ABLATIONS.items():
        for cw in PAPER_WINDOWS:
            yield f"lear_{name}_cw{cw}", cw, drop, DEFAULT_SPEC
    for cw in EXTRA_WINDOWS:
        yield f"lear_cw{cw}", cw, [], DEFAULT_SPEC
    for cw in (56, 84):
        yield f"lear_exoglags12_cw{cw}", cw, [], LAGS_D2
    # LightGBM challenger: longest LEAR window, retrained weekly, tuned hyperparameters.
    yield "lgbm_cw1456", 1456, [], DEFAULT_SPEC


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", nargs="*", help="experiment names to run")
    parser.add_argument("--n-jobs", type=int, default=None)
    args = parser.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    df = EpftoolboxZenodoSource("BE").load()
    for name, cw, drop, spec in experiments():
        path = OUT / f"{name}.csv"
        if path.exists() or (args.only and name not in args.only):
            continue
        start = time.time()
        if name.startswith("lgbm"):
            # Hyperparameters frozen beforehand by scripts/tune_lgbm.py --phase A.
            tuning = json.loads((OUT.parent / "lgbm_tuning_A.json").read_text())
            fc = lgbm_backtest(
                df.drop(columns=drop),
                BE_TEST_BEGIN,
                BE_TEST_END,
                tuning["best"],
                calibration_window=cw,
                spec=spec,
                n_jobs=args.n_jobs,
            )
        else:
            fc = lear_backtest(
                df.drop(columns=drop), BE_TEST_BEGIN, BE_TEST_END, cw, spec, n_jobs=args.n_jobs
            )
        fc.to_csv(path, float_format="%.6f")
        print(f"{name}: {len(fc)} days in {time.time() - start:.0f}s", flush=True)


if __name__ == "__main__":
    main()
