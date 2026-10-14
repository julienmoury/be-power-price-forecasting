"""Port check of the DNN: our port vs the original code.

Recalibrates each DNN on the days of tests/reference/original_dnn_reference.csv (made by
scripts/make_original_dnn_reference.py with the same seeds, deterministic TensorFlow ops
and one thread per process, on the same machine) and compares the forecasts (tolerance
1e-6 EUR/MWh) and the number of epochs. Writes results/dnn/port_check.json.
Usage: python scripts/check_dnn_port.py [--jobs N]
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
from run_dnn import _init_worker, environment

from be_power_forecast.config import RESULTS_DIR
from be_power_forecast.data.sources import EpftoolboxZenodoSource
from be_power_forecast.models.dnn import HourlyInputs, forecast_day, load_hyperparameters

REF = Path(__file__).resolve().parents[1] / "tests" / "reference" / "original_dnn_reference.csv"
TOLERANCE = 1e-6


def run(job):
    name, day = job
    inputs = HourlyInputs.from_frame(EpftoolboxZenodoSource("BE").load())
    t = inputs.dates.get_loc(pd.Timestamp(day))
    forecast, record, _ = forecast_day(inputs, t, load_hyperparameters()[name])
    return forecast, record["epochs"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--jobs", type=int, default=os.cpu_count())
    args = parser.parse_args()
    ref = pd.read_csv(REF)
    jobs = list(zip(ref.dnn, ref.date, strict=True))
    context = mp.get_context("spawn")
    with ProcessPoolExecutor(args.jobs, mp_context=context, initializer=_init_worker) as pool:
        results = list(pool.map(run, jobs))
    cases = []
    rows = (row for _, row in ref.iterrows())
    for (name, day), (forecast, epochs), row in zip(jobs, results, rows, strict=True):
        expected = row[[f"h{h}" for h in range(24)]].to_numpy(float)
        diff = float(np.max(np.abs(forecast - expected)))
        cases.append(
            {
                "dnn": name,
                "date": day,
                "max_abs_diff": diff,
                "epochs": epochs,
                "epochs_original": int(row.epochs),
                "ok": diff <= TOLERANCE and epochs == int(row.epochs),
            }
        )
        print(f"{name:9s} {day}: max |diff| {diff:.2e}, epochs {epochs} vs {int(row.epochs)}")
    out = {
        "tolerance": TOLERANCE,
        "all_ok": all(c["ok"] for c in cases),
        "cases": cases,
        "environment": environment(),
    }
    (RESULTS_DIR / "dnn").mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "dnn" / "port_check.json").write_text(json.dumps(out, indent=1) + "\n")
    print("port check:", "OK" if out["all_ok"] else "DRIFT")


if __name__ == "__main__":
    main()
