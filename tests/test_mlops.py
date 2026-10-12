import numpy as np
import pandas as pd
import pytest

from be_power_forecast.mlops import drift


def daily(values, start="2020-01-01"):
    return pd.Series(values, index=pd.date_range(start, periods=len(values)), dtype=float)


def test_daily_abs_error_is_mean_over_hours():
    idx = pd.date_range("2020-01-01", periods=2)
    real = pd.DataFrame(np.zeros((2, 24)), index=idx)
    pred = pd.DataFrame(np.r_[np.ones(24), np.arange(24)].reshape(2, 24), index=idx)
    assert drift.daily_abs_error(real, pred).tolist() == [1.0, 11.5]


def test_rolling_mae_starts_after_a_full_window():
    rng = np.random.default_rng(2026)
    err = daily(rng.gamma(2, 3, 100))
    rolled = drift.rolling_mae(err, window=30)
    assert rolled.index[0] == err.index[29] and len(rolled) == 71
    assert np.allclose(rolled.to_numpy(), err.rolling(30).mean().dropna().to_numpy())


def test_rolling_mae_skips_days_not_forecast():
    err = daily(np.arange(40.0)).drop(pd.Timestamp("2020-01-20"))
    rolled = drift.rolling_mae(err, window=30)
    # Window ending on 2020-01-30 holds 29 days (1 to 30 January minus the 20th).
    expected = np.mean([v for v in range(30) if v != 19])
    assert rolled.loc["2020-01-30"] == pytest.approx(expected)


def test_rolling_rmae_is_ratio_of_window_maes():
    rng = np.random.default_rng(2026)
    err, ref = daily(rng.gamma(2, 3, 60)), daily(rng.gamma(2, 4, 60))
    rolled = drift.rolling_rmae(err, ref, window=30)
    assert rolled.iloc[-1] == pytest.approx(err.iloc[-30:].mean() / ref.iloc[-30:].mean())
    assert len(rolled) == 31


def test_threshold_is_the_quantile():
    rolled = daily(np.arange(101.0))
    assert drift.threshold(rolled, 0.95) == pytest.approx(95.0)


def test_alert_episodes():
    rolled = daily([1, 5, 6, 1, 1, 7, 1, 8, 9]).drop(pd.Timestamp("2020-01-03"))
    episodes = drift.alert_episodes(rolled, 4.0)
    assert episodes == [
        {"start": "2020-01-02", "end": "2020-01-02", "days": 1},
        {"start": "2020-01-06", "end": "2020-01-06", "days": 1},
        {"start": "2020-01-08", "end": "2020-01-09", "days": 2},
    ]
    # A day not forecast inside a run does not split the episode.
    assert drift.alert_episodes(daily([5, 5, 5]).drop(pd.Timestamp("2020-01-02")), 4) == [
        {"start": "2020-01-01", "end": "2020-01-03", "days": 2}
    ]
    assert drift.alert_episodes(daily([1, 2]), 4) == []


def test_first_monthly_exceedance():
    idx = pd.date_range("2019-01-01", "2021-12-31")
    err = pd.Series(5.0, index=idx)
    err.loc["2021-03-01":"2021-03-31"] = 10.5  # first month above 2 x 5
    err.loc["2021-06-01":] = 20.0
    event = drift.first_monthly_exceedance(err, ("2019-01-01", "2020-12-31"), "2021-01-01")
    assert event == {
        "month": "2021-03",
        "known_on": "2021-03-31",
        "monthly_MAE": 10.5,
        "base_monthly_MAE": 5.0,
    }
    flat = pd.Series(5.0, index=idx)
    assert drift.first_monthly_exceedance(flat, ("2019-01-01", "2020-12-31"), "2021-01") is None


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
