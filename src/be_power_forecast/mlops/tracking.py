"""Experiment tracking: one MLflow run per backtest, in a local store under ``mlruns/``.

``results/metrics.json`` stays the only source of quoted numbers; MLflow is a browsable
log of the backtests (``mlflow ui --backend-store-uri sqlite:///mlruns/mlflow.db``).
MLflow 3 refuses the plain file store by default, so the store is a local SQLite file
(no server; git-ignored with the artifacts). Setting ``MLFLOW_TRACKING_URI`` (e.g.
``databricks``) sends the runs to another store instead, with ``MLFLOW_EXPERIMENT_PREFIX``
prepended to the experiment names (Databricks needs workspace paths such as
``/Users/<user>/be-power/``).
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from be_power_forecast.config import REPO_ROOT

TRACKING_DIR = REPO_ROOT / "mlruns"


def tracking_uri(root: Path = TRACKING_DIR) -> str:
    """``MLFLOW_TRACKING_URI`` if set, else the local SQLite store under ``root``."""
    return (
        os.environ.get("MLFLOW_TRACKING_URI") or f"sqlite:///{Path(root).resolve() / 'mlflow.db'}"
    )


def log_backtest(
    name: str,
    phase: str,
    params: dict,
    metrics: dict,
    forecast_path: Path,
    root: Path = TRACKING_DIR,
) -> str:
    """Log one backtest as a run named ``name`` in experiment ``phase_<phase>``.

    A previous run of the same name is deleted first, so re-logging a backtest keeps one
    run per backtest. Returns the run id.
    """
    from mlflow.entities import Metric, Param
    from mlflow.tracking import MlflowClient

    uri = tracking_uri(root)
    local = uri.startswith("sqlite:")
    if local:
        Path(root).mkdir(parents=True, exist_ok=True)
    client = MlflowClient(uri)
    experiment = os.environ.get("MLFLOW_EXPERIMENT_PREFIX", "") + f"phase_{phase}"
    exp = client.get_experiment_by_name(experiment)
    if exp:
        exp_id = exp.experiment_id
    else:
        artifacts = (Path(root) / "artifacts").resolve().as_uri() if local else None
        exp_id = client.create_experiment(experiment, artifacts)
    for old in client.search_runs([exp_id], f"attributes.run_name = '{name}'"):
        client.delete_run(old.info.run_id)
    path = Path(forecast_path).resolve()
    csv = str(path.relative_to(REPO_ROOT)) if path.is_relative_to(REPO_ROOT) else str(path)
    run = client.create_run(exp_id, run_name=name, tags={"forecast_csv": csv})
    now = int(time.time() * 1000)
    client.log_batch(
        run.info.run_id,
        metrics=[Metric(k, float(v), now, 0) for k, v in metrics.items()],
        params=[Param(k, str(v)) for k, v in {"phase": phase, **params}.items()],
    )
    client.set_terminated(run.info.run_id)
    return run.info.run_id
