"""Daily-recalibrated DNN backtests of Lago et al. (2021), with the full training record.

Every (DNN, test day) is one job: recalibrate on the 4-year window before the day, forecast
it, and write
* ``<record-dir>/<phase>/<dnn>/<date>.json``: forecast, seed, sample sizes, the training
  history (per epoch: training loss, validation loss, validation MAE), the epoch kept,
  SHA-256 of the input window, of the validation draw and of the final weights, run time,
  library versions, code commit
  (``-dirty`` if src/ or scripts/ had uncommitted changes);
* ``<record-dir>/<phase>/<dnn>/<date>.npz``: the final weights (``np.load`` + Keras
  ``set_weights`` restores the network that made the forecast).
Jobs whose JSON exists are skipped, so runs can be resumed and split across machines
(``--shard i/n`` runs every n-th job); the records of all shards are then collected:
``--collect`` writes the forecasts to results/forecasts/[phase_b/]dnn_<dnn>.csv and the
training records to results/dnn/<phase>/ (``summary_<dnn>.csv``: one row per day;
``history_<dnn>.csv.gz``: one row per epoch).

TensorFlow runs with deterministic ops and one thread per worker; the parallelism is across
jobs. Phase B reads the standard frame of scripts/build_phase_b.py.
Usage: python scripts/run_dnn.py --phase A|B [--dnn NAME ...] [--days N] [--shard i/n]
       [--jobs N] [--record-dir DIR] | --collect
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import platform
import subprocess
import time
from concurrent.futures import ProcessPoolExecutor
from importlib.metadata import version
from pathlib import Path

import numpy as np
import pandas as pd

from be_power_forecast.config import CACHE_DIR, PHASE_B_TEST, REPO_ROOT, RESULTS_DIR
from be_power_forecast.data.sources import (
    BE_TEST_BEGIN,
    BE_TEST_END,
    EpftoolboxZenodoSource,
    validate_standard_frame,
)
from be_power_forecast.models.dnn import (
    HourlyInputs,
    forecast_day,
    forecastable,
    load_hyperparameters,
)

RECORDS = REPO_ROOT / "artifacts" / "dnn"  # git-ignored, archived outside the repository
HOURS = [f"h{h}" for h in range(24)]


def load_phase(phase: str):
    if phase == "B":
        df = validate_standard_frame(
            pd.read_parquet(CACHE_DIR / "phase_b_FR.parquet"), allow_missing_days=True
        )
        return df, PHASE_B_TEST
    return EpftoolboxZenodoSource("BE").load(), (BE_TEST_BEGIN, BE_TEST_END)


def environment() -> dict:
    """Machine, library versions and code commit of a worker."""
    try:
        git = ["git", "-C", str(REPO_ROOT)]
        commit = subprocess.run([*git, "rev-parse", "HEAD"], capture_output=True, text=True)
        status = subprocess.run(
            [*git, "status", "--porcelain", "--", "src", "scripts"], capture_output=True, text=True
        )
        commit = commit.stdout.strip() + ("-dirty" if status.stdout.strip() else "")
    except OSError:
        commit = ""
    return {
        "python": platform.python_version(),
        "commit": os.environ.get("GIT_COMMIT", commit),
        **{lib: version(lib) for lib in ("tensorflow", "keras", "numpy", "scikit-learn")},
    }


def _init_worker() -> None:
    os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
    import tensorflow as tf

    tf.config.threading.set_intra_op_parallelism_threads(1)
    tf.config.threading.set_inter_op_parallelism_threads(1)
    tf.config.experimental.enable_op_determinism()


def run_job(job) -> str:
    phase, name, t, record_dir = job
    df, _ = load_phase(phase)
    inputs = HourlyInputs.from_frame(df)
    setting = load_hyperparameters()[name]
    start = time.time()
    _, record, weights = forecast_day(inputs, t, setting)
    record = {"phase": phase, "dnn": name, "trial_file": setting["trial_file"], **record}
    record["seconds"] = round(time.time() - start, 1)
    record["environment"] = environment()
    out = Path(record_dir) / phase / name / record["date"]
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out.with_suffix(".npz"), *weights)
    # JSON last: its presence marks the job as done.
    out.with_suffix(".json").write_text(json.dumps(record))
    return f"{name} {record['date']}: {record['epochs']} epochs, {record['seconds']}s"


def jobs(phase: str, names: list[str], record_dir: Path, days: int | None):
    df, (begin, end) = load_phase(phase)
    inputs = HourlyInputs.from_frame(df)
    dates = inputs.dates
    test = np.flatnonzero((dates >= pd.Timestamp(begin)) & (dates <= pd.Timestamp(end)))
    # Days that depend on a day dropped by the data rules are not forecast (as for LEAR).
    test = test[forecastable(inputs)[test]][:days]
    settings = load_hyperparameters()
    # Longest jobs (data augmentation) first, for load balancing.
    order = sorted(names, key=lambda n: not settings[n]["data_augmentation"])
    for name in order:
        for t in test:
            if not (record_dir / phase / name / f"{dates[t].date()}.json").exists():
                yield phase, name, int(t), str(record_dir)


def collect(phase: str, record_dir: Path) -> None:
    sub = "phase_b/" if phase == "B" else ""
    out = RESULTS_DIR / "dnn" / f"phase_{phase.lower()}"
    out.mkdir(parents=True, exist_ok=True)
    inputs = HourlyInputs.from_frame(load_phase(phase)[0])
    keep = {str(d.date()) for d in inputs.dates[forecastable(inputs)]}
    for name in load_hyperparameters():
        files = sorted((record_dir / phase / name).glob("*.json"))
        if not files:
            continue
        # Records of days the rule excludes (made before it existed) are not collected.
        skipped = [f.stem for f in files if f.stem not in keep]
        if skipped:
            print(f"{name}: not collected (depends on a dropped day): {', '.join(skipped)}")
        records = [json.loads(f.read_text()) for f in files if f.stem in keep]
        index = pd.DatetimeIndex([r["date"] for r in records], name="Date")
        fc = pd.DataFrame([r["forecast"] for r in records], index=index, columns=HOURS)
        fc.to_csv(RESULTS_DIR / "forecasts" / f"{sub}dnn_{name}.csv", float_format="%.6f")
        keys = ["seed", "n_features", "n_train", "n_val", "epochs", "best_epoch", "seconds"]
        keys += ["data_sha256", "validation_sha256", "weights_sha256"]
        summary = pd.DataFrame([{k: r[k] for k in keys} for r in records], index=index)
        env = pd.DataFrame([r["environment"] for r in records], index=index)
        summary.join(env).to_csv(out / f"summary_{name}.csv")
        history = pd.DataFrame(
            [(r["date"], e, *h) for r in records for e, h in enumerate(r["history"], start=1)],
            columns=["date", "epoch", "train_loss", "val_loss", "val_mae"],
        )
        history.to_csv(out / f"history_{name}.csv.gz", index=False, float_format="%.7g")
        print(f"{name}: {len(records)} days collected")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=["A", "B"], default="A")
    parser.add_argument("--dnn", nargs="*", help="DNNs to run (default: the four)")
    parser.add_argument("--days", type=int, help="only the first N test days (timing tests)")
    parser.add_argument("--shard", default="0/1", help="i/n: run every n-th job from the i-th")
    parser.add_argument("--jobs", type=int, default=os.cpu_count())
    parser.add_argument("--record-dir", type=Path, default=RECORDS)
    parser.add_argument("--collect", action="store_true")
    args = parser.parse_args()
    if args.collect:
        collect(args.phase, args.record_dir)
        return
    names = args.dnn or list(load_hyperparameters())
    i, n = map(int, args.shard.split("/"))
    todo = list(jobs(args.phase, names, args.record_dir, args.days))[i::n]
    print(f"{len(todo)} jobs on {args.jobs} workers", flush=True)
    context = mp.get_context("spawn")  # TensorFlow is not fork-safe
    with ProcessPoolExecutor(args.jobs, mp_context=context, initializer=_init_worker) as pool:
        for line in pool.map(run_job, todo):
            print(line, flush=True)


if __name__ == "__main__":
    main()
