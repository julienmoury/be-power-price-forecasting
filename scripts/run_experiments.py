"""Run every LEAR backtest used in the README and save forecasts to results/forecasts/.

Each experiment is skipped if its CSV already exists, so the script can be resumed.
Usage: python scripts/run_experiments.py [--only NAME ...] [--n-jobs N]
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from be_power_forecast.backtest import lear_backtest
from be_power_forecast.data.sources import BE_TEST_BEGIN, BE_TEST_END, EpftoolboxZenodoSource

OUT = Path(__file__).resolve().parents[1] / "results" / "forecasts"

PAPER_WINDOWS = (56, 84, 1092, 1456)
EXTRA_WINDOWS = (28, 182, 364, 728)

# name -> columns dropped from the standard frame
ABLATIONS = {
    "no_exog": ["Generation forecast FR", "Load forecast FR"],
    "no_load_fr": ["Load forecast FR"],
    "no_gen_fr": ["Generation forecast FR"],
}


def experiments():
    for cw in PAPER_WINDOWS:
        yield f"lear_cw{cw}", cw, []
    for name, drop in ABLATIONS.items():
        for cw in PAPER_WINDOWS:
            yield f"lear_{name}_cw{cw}", cw, drop
    for cw in EXTRA_WINDOWS:
        yield f"lear_cw{cw}", cw, []


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", nargs="*", help="experiment names to run")
    parser.add_argument("--n-jobs", type=int, default=None)
    args = parser.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    df = EpftoolboxZenodoSource("BE").load()
    for name, cw, drop in experiments():
        path = OUT / f"{name}.csv"
        if path.exists() or (args.only and name not in args.only):
            continue
        start = time.time()
        fc = lear_backtest(
            df.drop(columns=drop), BE_TEST_BEGIN, BE_TEST_END, cw, n_jobs=args.n_jobs
        )
        fc.to_csv(path, float_format="%.6f")
        print(f"{name}: {len(fc)} days in {time.time() - start:.0f}s", flush=True)


if __name__ == "__main__":
    main()
