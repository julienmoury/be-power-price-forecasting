"""Choose the LightGBM configuration on 2015-2016, before the phase B test period.

Each configuration of the grid is backtested on config.LGBM_TUNING with the phase B frame
(data/cache/phase_b_FR.parquet), retrained every week to save time (the test retrains
every day), and recorded as one MLflow run: its parameters, its MAE and its duration. The
best MAE is then frozen by hand in models/lgbm.py (CONFIG); nothing of 2017-2026 is used.
Writes results/lgbm_tuning.json; configurations already in it are skipped (resumable).
MLflow tracks to mlruns/ (git-ignored); browse with
``mlflow ui --backend-store-uri sqlite:///mlruns/mlflow.db``.
Usage: python scripts/tune_lgbm.py [--n-jobs N]   (needs pip install -e ".[experiments]")
"""

from __future__ import annotations

import argparse
import itertools
import json
import time

import mlflow
import pandas as pd

from be_power_forecast.backtest import daily_prices
from be_power_forecast.config import CACHE_DIR, LGBM_TUNING, REPO_ROOT, RESULTS_DIR
from be_power_forecast.data.sources import validate_standard_frame
from be_power_forecast.evaluation.metrics import mae
from be_power_forecast.models.lgbm import FIXED, lgbm_backtest

GRID = {
    "calibration_window": (364, 728, 1456),
    "num_leaves": (15, 31),
    "learning_rate": (0.03, 0.1),
    "n_estimators": (300, 600),
}
RETRAIN_EVERY = 7
OUT = RESULTS_DIR / "lgbm_tuning.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-jobs", type=int, default=None)
    args = parser.parse_args()
    df = validate_standard_frame(
        pd.read_parquet(CACHE_DIR / "phase_b_FR.parquet"), allow_missing_days=True
    )
    begin, end = LGBM_TUNING
    prices = daily_prices(df, begin, end)
    out = json.loads(OUT.read_text()) if OUT.exists() else {"scores": []}
    out.update(
        tuning_period=[begin, end],
        retrain_every_days=RETRAIN_EVERY,
        grid={k: list(v) for k, v in GRID.items()},
    )
    done = [{k: s[k] for k in GRID} for s in out["scores"]]
    (REPO_ROOT / "mlruns").mkdir(exist_ok=True)
    mlflow.set_tracking_uri(f"sqlite:///{REPO_ROOT / 'mlruns' / 'mlflow.db'}")
    mlflow.set_experiment("lgbm-tuning-2015-2016")
    for values in itertools.product(*GRID.values()):
        config = dict(zip(GRID, values, strict=True))
        if config in done:
            continue
        with mlflow.start_run(run_name=" ".join(f"{k}={v}" for k, v in config.items())):
            mlflow.log_params({**config, **FIXED, "retrain_every_days": RETRAIN_EVERY})
            start = time.time()
            fc = lgbm_backtest(df, begin, end, config, RETRAIN_EVERY, n_jobs=args.n_jobs)
            real = prices.loc[fc.index]
            score = {
                "MAE": mae(real, fc),
                **{f"MAE {y}": mae(real.loc[y], fc.loc[y]) for y in ("2015", "2016")},
                "seconds": round(time.time() - start),
            }
            mlflow.log_metrics({k.replace(" ", "_"): v for k, v in score.items()})
        out["scores"].append({**config, **score, "days": len(fc)})
        out["best"] = min(out["scores"], key=lambda s: s["MAE"])
        OUT.write_text(json.dumps(out, indent=1) + "\n")
        print(f"{config}: MAE {score['MAE']:.3f} in {score['seconds']}s", flush=True)


if __name__ == "__main__":
    main()
