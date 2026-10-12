import pytest


def test_log_backtest_keeps_one_run_per_backtest(tmp_path):
    pytest.importorskip("mlflow")
    from mlflow.tracking import MlflowClient

    from be_power_forecast.mlops.tracking import log_backtest, tracking_uri

    csv = tmp_path / "lear_cw56.csv"
    csv.write_text("")
    params = {"calibration_window": 56}
    log_backtest("lear_cw56", "B", params, {"MAE": 2.0}, csv, root=tmp_path / "mlruns")
    run_id = log_backtest("lear_cw56", "B", params, {"MAE": 1.5}, csv, root=tmp_path / "mlruns")
    client = MlflowClient(tracking_uri(tmp_path / "mlruns"))
    exp = client.get_experiment_by_name("phase_B")
    runs = client.search_runs([exp.experiment_id])
    assert [r.info.run_id for r in runs] == [run_id]
    run = runs[0]
    assert run.data.metrics == {"MAE": 1.5}
    assert run.data.params == {"phase": "B", "calibration_window": "56"}
    assert run.data.tags["forecast_csv"] == str(csv.resolve())


def test_tracking_uri_from_environment(tmp_path, monkeypatch):
    from be_power_forecast.mlops.tracking import tracking_uri

    monkeypatch.delenv("MLFLOW_TRACKING_URI", raising=False)
    assert tracking_uri(tmp_path) == f"sqlite:///{tmp_path.resolve() / 'mlflow.db'}"
    monkeypatch.setenv("MLFLOW_TRACKING_URI", "databricks")
    assert tracking_uri(tmp_path) == "databricks"
