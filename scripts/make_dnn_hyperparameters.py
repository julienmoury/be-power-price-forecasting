"""Extract the published hyperparameters of the four BE DNNs of Lago et al. (2021).

Reads the hyperopt trial files of the paper's code (examples/experimental_files,
commit 47d6e06), keeps the best trial of each, decodes it exactly as
``format_best_trial`` of the paper's code does, and writes
data/raw/dnn_hyperparameters_BE.json (with the SHA-256 of each trial file).

Reproducibility (not part of the package or CI): the trial files are hyperopt ``Trials``
pickles, so this needs ``pip install hyperopt`` and a clone of the paper's code:

    # the paper's code, checked out at commit 47d6e06 in ./epftoolbox
    EPFTOOLBOX_DIR=epftoolbox python scripts/make_dnn_hyperparameters.py
"""

from __future__ import annotations

import hashlib
import json
import os
import pickle
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EPF = Path(os.environ.get("EPFTOOLBOX_DIR", "epftoolbox"))
OUT = REPO / "data" / "raw" / "dnn_hyperparameters_BE.json"

# Trial-file suffix -> (shuffle_train, data_augmentation), as in the file names built by
# Paper's code: '_SF' * shuffle_train + '_DA' * data_augmentation.
NAMES = {"SF": (1, 0), "SF_DA": (1, 1), "SF_SF": (2, 0), "SF_SF_DA": (2, 1)}
CHOICES = {
    "activation": ["relu", "softplus", "tanh", "selu", "LeakyReLU", "PReLU", "sigmoid"],
    "init": [
        "Orthogonal",
        "lecun_uniform",
        "glorot_uniform",
        "glorot_normal",
        "he_uniform",
        "he_normal",
    ],
    "scaleX": ["No", "Norm", "Norm1", "Std", "Median", "Invariant"],
    "scaleY": ["No", "Norm", "Norm1", "Std", "Median", "Invariant"],
    "reg": [None, "l1"],
}


def main() -> None:
    out = {}
    for name, (shuffle_train, data_augmentation) in NAMES.items():
        path = (
            EPF
            / "examples"
            / "experimental_files"
            / f"DNN_hyperparameters_nl2_datBE_YT2_{name}_CW4_1"
        )
        raw = path.read_bytes()
        best = pickle.loads(raw).best_trial
        hp = {k: (v[0] if len(v) else 0) for k, v in best["misc"]["vals"].items()}
        hp = {k: CHOICES[k][int(v)] if k in CHOICES else v for k, v in hp.items()}
        hp = {k: (v.item() if hasattr(v, "item") else v) for k, v in hp.items()}
        out[name] = {
            "trial_file": path.name,
            "trial_file_sha256": hashlib.sha256(raw).hexdigest(),
            "shuffle_train": shuffle_train,
            "data_augmentation": bool(data_augmentation),
            "validation_mae_hyperopt": float(best["result"]["MAE Val"]),
            "hyperparameters": dict(sorted(hp.items())),
        }
    OUT.write_text(json.dumps(out, indent=2) + "\n")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
