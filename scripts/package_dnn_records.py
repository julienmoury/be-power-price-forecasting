"""Pack the per-day DNN training records for a GitHub Release, and check them.

Records are written by scripts/run_dnn.py to artifacts/dnn/<phase>/<dnn>/<date>.{json,npz}.
This script first checks every record: its weights file restores the hash written in the
JSON (``weights_sha256``) and the forecast equals the collected CSV. It then packs the
records of each (phase, DNN) into tar archives of less than 2 GiB (the per-file limit of
release assets) in artifacts/release/, and writes results/dnn/archive_manifest.json with
the SHA-256, size and first/last day of every archive. Uploading is a separate, manual
step (it publishes the files):

    gh release create dnn-records-v1 artifacts/release/*.tar --title "DNN training records"

Usage: python scripts/package_dnn_records.py [--phase A B] [--record-dir DIR]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tarfile
from pathlib import Path

import numpy as np
import pandas as pd
from run_dnn import RECORDS

from be_power_forecast.config import RESULTS_DIR
from be_power_forecast.models.dnn import load_hyperparameters, weights_sha256

LIMIT = 1900 * 2**20  # bytes per archive, below the 2 GiB limit of release assets
OUT = RECORDS.parent / "release"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(2**20), b""):
            digest.update(block)
    return digest.hexdigest()


def check(phase: str, name: str, days: list[Path]) -> None:
    sub = "phase_b/" if phase == "B" else ""
    csv = RESULTS_DIR / "forecasts" / f"{sub}dnn_{name}.csv"
    collected = pd.read_csv(csv, index_col=0) if csv.exists() else None
    for js in days:
        record = json.loads(js.read_text())
        with np.load(js.with_suffix(".npz")) as npz:
            weights = [npz[f"arr_{i}"] for i in range(len(npz.files))]
        if weights_sha256(weights) != record["weights_sha256"]:
            raise ValueError(f"{js}: weights do not match their hash")
        # Days not collected (excluded by the forecastable-day rule) keep only the hash check.
        if (
            collected is not None
            and record["date"] in collected.index
            and not np.allclose(
                collected.loc[record["date"]].to_numpy(float), record["forecast"], atol=1e-6
            )
        ):
            raise ValueError(f"{js}: forecast differs from {csv.name}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", nargs="*", default=["A", "B"])
    parser.add_argument("--record-dir", type=Path, default=RECORDS)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = []
    for phase in args.phase:
        for name in load_hyperparameters():
            days = sorted((args.record_dir / phase / name).glob("*.json"))
            if not days:
                continue
            check(phase, name, days)
            chunks, size = [[]], 0
            for js in days:
                n = js.stat().st_size + js.with_suffix(".npz").stat().st_size
                if size + n > LIMIT and chunks[-1]:
                    chunks.append([])
                    size = 0
                chunks[-1].append(js)
                size += n
            for k, chunk in enumerate(chunks, start=1):
                path = OUT / f"dnn_phase_{phase.lower()}_{name}_{k:02d}.tar"
                with tarfile.open(path, "w") as tar:
                    for js in chunk:
                        for f in (js, js.with_suffix(".npz")):
                            tar.add(f, arcname=f"{phase}/{name}/{f.name}")
                manifest.append(
                    {
                        "file": path.name,
                        "sha256": sha256(path),
                        "bytes": path.stat().st_size,
                        "days": len(chunk),
                        "first": chunk[0].stem,
                        "last": chunk[-1].stem,
                    }
                )
                print(f"{path.name}: {len(chunk)} days, {path.stat().st_size / 2**20:.0f} MiB")
    out = RESULTS_DIR / "dnn" / "archive_manifest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=1) + "\n")


if __name__ == "__main__":
    main()
