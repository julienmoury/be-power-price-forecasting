"""Choose the LightGBM hyperparameters of a phase by walk-forward grid search, then freeze them.

The search runs on the 364 days before the test period (config.TUNING_PERIODS), with weekly
retraining as in the test, and writes results/lgbm_tuning_<phase>.json (chosen parameters
and the MAE of every grid point). The test runs read that file; nothing of the test period
enters the search.

Usage: python scripts/tune_lgbm.py --phase A [--n-jobs N]
"""

from __future__ import annotations

import argparse
import json
import time

import pandas as pd

from be_power_forecast.config import CACHE_DIR, RESULTS_DIR, TUNING_PERIODS, TUNING_WINDOW
from be_power_forecast.data.sources import EpftoolboxZenodoSource
from be_power_forecast.models.challenger import GRID, tune


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=sorted(TUNING_PERIODS), required=True)
    parser.add_argument("--n-jobs", type=int, default=None)
    args = parser.parse_args()
    if args.phase == "A":
        df = EpftoolboxZenodoSource("BE").load()
    else:
        df = pd.read_parquet(CACHE_DIR / "phase_b_FR.parquet")  # written by build_phase_b.py
    begin, end = TUNING_PERIODS[args.phase]
    start = time.time()
    best, scores = tune(df, begin, end, TUNING_WINDOW, n_jobs=args.n_jobs)
    out = {
        "phase": args.phase,
        "tuning_period": [begin, end],
        "calibration_window": TUNING_WINDOW,
        "retrain_every_days": 7,
        "grid": {k: list(v) for k, v in GRID.items()},
        "best": best,
        "scores": scores,
        "seconds": round(time.time() - start),
    }
    path = RESULTS_DIR / f"lgbm_tuning_{args.phase}.json"
    path.write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
