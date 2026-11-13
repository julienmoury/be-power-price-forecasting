"""Compute every number and figure quoted in the README from results/forecasts/*.csv.

Writes results/summary.md (tables), results/metrics.json and results/figures/*.png.
Experiments whose forecasts are missing are reported as missing, never filled in.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from be_power_forecast.backtest import daily_prices
from be_power_forecast.config import CACHE_DIR, PHASE_B_TEST, QUARTER_HOUR_START, TZ
from be_power_forecast.data.calendar import intra_hour_deviation
from be_power_forecast.data.sources import (
    BE_TEST_BEGIN,
    BE_TEST_END,
    EntsoeSource,
    LagoZenodoSource,
)
from be_power_forecast.evaluation.dm import dm_matrix, dm_test
from be_power_forecast.evaluation.gw import gw_matrix, gw_test
from be_power_forecast.evaluation.metrics import mae, naive_forecast, rmae, rmse, smape
from be_power_forecast.models.lear import ensemble
from be_power_forecast.readme import render

ROOT = Path(__file__).resolve().parents[1]
FC = ROOT / "results" / "forecasts"
FIG = ROOT / "results" / "figures"
PUBLISHED = ROOT / "tests" / "reference" / "Forecasts_BE_DNN_LEAR_ensembles.csv"

PAPER_WINDOWS = [56, 84, 1092, 1456]

# Reference palette (dataviz skill, light mode): categorical slots 1-3 + neutral ink.
BLUE, ORANGE, GREY, INK = "#2a78d6", "#eb6834", "#8a8984", "#52514e"
AQUA = "#1baf7a"  # categorical slot 3
YELLOW = "#eda100"  # categorical slot 4


def load(name: str) -> pd.DataFrame | None:
    path = FC / f"{name}.csv"
    if not path.exists():
        return None
    return pd.read_csv(path, index_col=0, parse_dates=True)


def scores(real: pd.DataFrame, pred: pd.DataFrame) -> dict:
    return {
        "MAE": mae(real, pred),
        "RMSE": rmse(real, pred),
        "sMAPE_pct": 100 * smape(real, pred),
        "rMAE": rmae(real, pred),
    }


def fmt_table(df: pd.DataFrame, digits: int = 2) -> str:
    cols = ["", *df.columns]
    lines = ["| " + " | ".join(map(str, cols)) + " |", "|" + "---|" * len(cols)]
    for idx, row in df.iterrows():
        cells = [f"{v:.{digits}f}" if isinstance(v, float) else str(v) for v in row]
        lines.append("| " + " | ".join([str(idx), *cells]) + " |")
    return "\n".join(lines)


def style(ax):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.spines["left"].set_color(GREY)
    ax.spines["bottom"].set_color(GREY)
    ax.tick_params(colors=INK, labelsize=9)
    ax.grid(axis="y", color="#e4e3df", linewidth=0.8)
    ax.set_axisbelow(True)


DNNS = {"SF": "DNN 1", "SF_DA": "DNN 2", "SF_SF": "DNN 3", "SF_SF_DA": "DNN 4"}


def dnn_block(phase: str, real, lear_ens, naive, missing: list[str], published=None):
    """Our four DNNs and their ensemble on the days of ``real``; ``None`` if any is missing.

    ``published``: the paper's daily forecasts (phase A), keyed as in the published file
    ("DNN 1".."DNN 4" follow the order of the trial files: SF, SF_DA, SF_SF, SF_SF_DA).
    """
    sub = "phase_b/" if phase == "B" else ""
    fcs = {n: load(f"{sub}dnn_{n}") for n in DNNS}
    absent = [f"{sub}dnn_{n}" for n, f in fcs.items() if f is None]
    if absent:
        missing += absent
        return None
    fcs = {n: f.loc[real.index] for n, f in fcs.items()}
    ens = pd.DataFrame(
        ensemble([f.to_numpy() for f in fcs.values()]), index=real.index, columns=real.columns
    )
    R, E, L, N = (x.to_numpy() for x in (real, ens, lear_ens, naive))
    out = {
        "accuracy": {
            **{f"DNN {n}": scores(real, f) for n, f in fcs.items()},
            "DNN Ens.": scores(real, ens),
        },
        "tests": {
            "gw_p_dnn_better_than_lear": float(gw_test(R, L, E)[1]),
            "gw_p_lear_better_than_dnn": float(gw_test(R, E, L)[1]),
            "gw_p_dnn_better_than_naive": float(gw_test(R, N, E)[1]),
            "dm_p_dnn_better_than_lear": float(dm_test(R, L, E)[1]),
            "dm_p_lear_better_than_dnn": float(dm_test(R, E, L)[1]),
            "dm_p_dnn_better_than_naive": float(dm_test(R, N, E)[1]),
        },
    }
    if published is not None:
        P = published["DNN Ensemble"].to_numpy()
        out["published"] = {
            **{f"DNN {n} MAE": mae(real, published[k]) for n, k in DNNS.items()},
            **{f"DNN {n} gap to published": mae(published[k], fcs[n]) for n, k in DNNS.items()},
            "DNN Ens. MAE": mae(real, published["DNN Ensemble"]),
            "mean abs gap of the ensemble to published": mae(published["DNN Ensemble"], ens),
            "gw_p_ours_better_than_published": float(gw_test(R, P, E)[1]),
            "gw_p_published_better_than_ours": float(gw_test(R, E, P)[1]),
            "dm_p_ours_better_than_published": float(dm_test(R, P, E)[1]),
            "dm_p_published_better_than_ours": float(dm_test(R, E, P)[1]),
        }
    # Training records (scripts/run_dnn.py --collect): where and with what each day was run.
    summaries = [
        ROOT / "results" / "dnn" / f"phase_{phase.lower()}" / f"summary_{n}.csv" for n in DNNS
    ]
    if all(p.exists() for p in summaries):
        rec = pd.concat([pd.read_csv(p) for p in summaries])
        out["training"] = {
            "trainings": len(rec),
            "epochs_mean": float(rec["epochs"].mean()),
            "commits": sorted(c[:7] for c in rec["commit"].unique()),
            "tensorflow": sorted(rec["tensorflow"].unique()),
            "vcpu_hours": float(rec["seconds"].sum() / 3600),
        }
    return out, ens


def lgbm_block(real, lear_ens, dnn_ens, naive, missing: list[str]) -> dict | None:
    """The LightGBM challenger against the paper's models on the phase B test days, with
    its tuning on 2015-2016 (scripts/tune_lgbm.py); ``None`` if a piece is missing."""
    fc, tuning = load("phase_b/lgbm"), ROOT / "results" / "lgbm_tuning.json"
    if fc is None or dnn_ens is None or not tuning.exists():
        missing.append("phase_b/lgbm, results/lgbm_tuning.json or the DNN forecasts")
        return None
    tuning = json.loads(tuning.read_text())
    fc = fc.loc[real.index]
    R, F = real.to_numpy(), fc.to_numpy()
    others = {"lear": lear_ens, "dnn": dnn_ens, "naive": naive}
    tests = {}
    for name, other in others.items():
        tests[f"gw_p_lgbm_better_than_{name}"] = float(gw_test(R, other.to_numpy(), F)[1])
        tests[f"gw_p_{name}_better_than_lgbm"] = float(gw_test(R, F, other.to_numpy())[1])
    by_year = lambda f: (real - f).abs().mean(axis=1).groupby(real.index.year).mean()  # noqa: E731
    years = pd.DataFrame(
        {"LightGBM": by_year(fc), "LEAR ens.": by_year(lear_ens), "DNN ens.": by_year(dnn_ens)}
    )
    return {
        "tuning": {
            "period": tuning["tuning_period"],
            "configurations": len(tuning["scores"]),
            "retrain_every_days": tuning["retrain_every_days"],
            "best": tuning["best"],
            "worst_MAE": max(t["MAE"] for t in tuning["scores"]),
        },
        "accuracy": scores(real, fc),
        "gain vs naive %": 100 * (1 - mae(real, fc) / mae(real, naive)),
        "tests": tests,
        "MAE by year": {str(y): row.to_dict() for y, row in years.iterrows()},
    }


def phase_b(missing: list[str]) -> tuple[dict | None, list[str], tuple | None]:
    """Phase B: the paper's protocol on the joined BE.csv + ENTSO-E frame, 2017-2026.

    Also returns the evaluated (real, LEAR ensemble, naive) daily frames for the figure.
    """
    frame_path = CACHE_DIR / "phase_b_FR.parquet"
    fcs = {cw: load(f"phase_b/lear_cw{cw}") for cw in PAPER_WINDOWS}
    absent = [f"phase_b/lear_cw{cw}" for cw, f in fcs.items() if f is None]
    if absent or not frame_path.exists():
        missing += absent or ["data/cache/phase_b_FR.parquet (run build_phase_b.py)"]
        return None, [], None
    df = pd.read_parquet(frame_path)
    begin, end = PHASE_B_TEST
    hist = daily_prices(df, pd.Timestamp(begin) - pd.Timedelta(days=7), end)
    naive = naive_forecast(hist)
    days = fcs[PAPER_WINDOWS[0]].loc[begin:end].index
    ens = pd.DataFrame(
        ensemble([fcs[cw].loc[days].to_numpy() for cw in PAPER_WINDOWS]),
        index=days,
        columns=fcs[PAPER_WINDOWS[0]].columns,
    )
    real = hist.reindex(days)
    naive = naive.reindex(days)
    # Days evaluated: forecast by LEAR and with a naive reference (dropped days excluded).
    ok = real.notna().all(axis=1) & naive.notna().all(axis=1)
    real, naive, ens = real[ok], naive[ok], ens[ok]
    fcs = {cw: f.loc[real.index] for cw, f in fcs.items()}
    accuracy = {
        "mean price": float(real.to_numpy().mean()),
        "negative hours %": float(100 * (real.to_numpy() < 0).mean()),
        "MAE naive": mae(real, naive),
        **{f"MAE LEAR {cw}": mae(real, fcs[cw]) for cw in PAPER_WINDOWS},
        "MAE LEAR ens.": mae(real, ens),
        "RMSE LEAR ens.": rmse(real, ens),
        "sMAPE % LEAR ens.": 100 * smape(real, ens),
        "MAE ens. / MAE naive": mae(real, ens) / mae(real, naive),
        "gain vs naive (EUR per MWh)": mae(real, naive) - mae(real, ens),
        "gain vs naive %": 100 * (1 - mae(real, ens) / mae(real, naive)),
        "GW p (ens. better than naive)": float(gw_test(real, naive, ens)[1]),
        "DM p (ens. better than naive)": float(dm_test(real, naive, ens)[1]),
    }
    out: dict = {
        "test_period": [begin, end],
        "test_days": len(pd.date_range(begin, end)),
        "evaluated_days": len(real),
        "accuracy": accuracy,
    }
    dnn = dnn_block("B", real, ens, naive, missing)
    if dnn is not None:
        out["dnn"] = dnn[0]
    dnn_ens = None if dnn is None else dnn[1]
    lgbm = lgbm_block(real, ens, dnn_ens, naive, missing)
    if lgbm is not None:
        out["lgbm"] = lgbm
    md = [
        f"## Phase B: 4-window LEAR on BE.csv + ENTSO-E data, {begin} to {end}",
        f"{len(real)} of {out['test_days']} test days evaluated (days depending on a "
        "dropped day are not forecast).",
        "```",
        json.dumps(accuracy, indent=1),
        "```",
        "",
    ]
    if "dnn" in out:
        md += ["### Phase B: our DNNs", "```", json.dumps(out["dnn"], indent=1), "```", ""]
    if "lgbm" in out:
        md += ["### Phase B: LightGBM challenger (beyond the paper)", "```"]
        md += [json.dumps(out["lgbm"], indent=1), "```", ""]
    lgbm_fc = None if lgbm is None else load("phase_b/lgbm").loc[real.index]
    return out, md, (real, ens, naive, dnn_ens, lgbm_fc)


def _xy(series: pd.Series):
    return series.index, series.to_numpy()


def monthly_figure(phase_a: tuple, phase_b_frames: tuple | None) -> None:
    """Monthly MAE of the LEAR and DNN ensembles and the naive forecast, phase A then B,
    and of the LightGBM challenger on phase B."""
    frames = [phase_a] if phase_b_frames is None else [phase_a, phase_b_frames]
    real, ens, naive = (pd.concat(parts) for parts in zip(*(f[:3] for f in frames), strict=True))
    monthly = lambda f: (real - f).abs().mean(axis=1).resample("MS").mean()  # noqa: E731
    fig, ax = plt.subplots(figsize=(7.5, 3.6), dpi=150)
    style(ax)
    ax.plot(*_xy(monthly(naive)), color=ORANGE, lw=1.8, label="Naive benchmark")
    ax.plot(*_xy(monthly(ens)), color=BLUE, lw=1.8, label="LEAR ensemble")
    # DNN ensemble, when both phases (or phase A alone) have it.
    if all(len(f) > 3 and f[3] is not None for f in frames):
        dnn = pd.concat([f[3] for f in frames])
        ax.plot(*_xy(monthly(dnn)), color=AQUA, lw=1.8, label="DNN ensemble")
    if phase_b_frames is not None and len(phase_b_frames) > 4 and phase_b_frames[4] is not None:
        lgbm = phase_b_frames[4]
        err = (real.loc[lgbm.index] - lgbm).abs().mean(axis=1).resample("MS").mean()
        ax.plot(*_xy(err), color=YELLOW, lw=1.8, label="LightGBM (challenger)")
    if phase_b_frames is not None:
        start = phase_b_frames[0].index[0]
        ax.axvline(start, color=GREY, lw=1, ls=":")
        ax.text(start, ax.get_ylim()[1], " extension →", color=INK, fontsize=8, va="top")
        ax.text(
            start,
            ax.get_ylim()[1],
            "← paper test period ",
            color=INK,
            fontsize=8,
            va="top",
            ha="right",
        )
    ax.set_ylabel("Monthly MAE (EUR/MWh)", color=INK)
    ax.set_title("Belgian day-ahead price: monthly forecast error", color=INK, fontsize=10)
    ax.legend(frameon=False, fontsize=8, loc="upper left", bbox_to_anchor=(0, 0.9))
    fig.tight_layout()
    fig.savefig(FIG / "monthly_mae.png")
    plt.close(fig)


def main() -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    df = LagoZenodoSource("BE").load()
    real = daily_prices(df, BE_TEST_BEGIN, BE_TEST_END)
    # Naive forecast needs the week before the test period.
    hist = daily_prices(df, pd.Timestamp(BE_TEST_BEGIN) - pd.Timedelta(days=7), BE_TEST_END)
    naive = naive_forecast(hist).loc[real.index]

    out: dict = {"test_period": [BE_TEST_BEGIN, BE_TEST_END], "n_days": len(real)}
    md: list[str] = []
    missing = []

    # ---- 1. Reproduction: our LEAR vs the forecasts published with the paper ----------------
    pub = pd.read_csv(PUBLISHED, index_col=0, parse_dates=True)
    pub_daily = {
        c: pd.DataFrame(pub[c].to_numpy().reshape(-1, 24), index=real.index, columns=real.columns)
        for c in pub.columns
    }
    assert np.allclose(pub_daily["Real price"].to_numpy(), real.to_numpy())

    ours = {cw: load(f"lear_cw{cw}") for cw in PAPER_WINDOWS}
    missing += [f"lear_cw{cw}" for cw, f in ours.items() if f is None]
    have_paper = all(ours[cw] is not None for cw in PAPER_WINDOWS)
    rows = {}
    for cw in PAPER_WINDOWS:
        if ours[cw] is None:
            continue
        rows[f"LEAR {cw}"] = {
            "MAE (ours)": mae(real, ours[cw]),
            "MAE (published)": mae(real, pub_daily[f"LEAR {cw}"]),
            "sMAPE % (ours)": 100 * smape(real, ours[cw]),
            "sMAPE % (published)": 100 * smape(real, pub_daily[f"LEAR {cw}"]),
            "mean abs gap to published": mae(pub_daily[f"LEAR {cw}"], ours[cw]),
        }
    if have_paper:
        ens = pd.DataFrame(
            ensemble([ours[cw].to_numpy() for cw in PAPER_WINDOWS]),
            index=real.index,
            columns=real.columns,
        )
        rows["LEAR Ensemble"] = {
            "MAE (ours)": mae(real, ens),
            "MAE (published)": mae(real, pub_daily["LEAR Ensemble"]),
            "sMAPE % (ours)": 100 * smape(real, ens),
            "sMAPE % (published)": 100 * smape(real, pub_daily["LEAR Ensemble"]),
            "mean abs gap to published": mae(pub_daily["LEAR Ensemble"], ens),
        }
    for cw in (56, 84):
        f = load(f"lear_exoglags12_cw{cw}")
        if f is None:
            missing.append(f"lear_exoglags12_cw{cw}")
            continue
        rows[f"LEAR {cw}, pre-2024 exogenous lags (d-1, d-2)"] = {
            "MAE (ours)": mae(real, f),
            "MAE (published)": mae(real, pub_daily[f"LEAR {cw}"]),
            "sMAPE % (ours)": 100 * smape(real, f),
            "sMAPE % (published)": 100 * smape(real, pub_daily[f"LEAR {cw}"]),
            "mean abs gap to published": mae(pub_daily[f"LEAR {cw}"], f),
        }
    repro = pd.DataFrame(rows).T
    out["reproduction"] = repro.to_dict(orient="index")
    md += ["## Reproduction of Lago et al. (2021), BE test period", fmt_table(repro, 3), ""]

    if not have_paper:
        md.append(f"Missing experiments: {missing}")
        (ROOT / "results" / "summary.md").write_text("\n".join(md))
        print("\n".join(md))
        return

    # ---- 2. Headline: LEAR vs naive, ensemble vs single windows ------------------------------
    models = {"Naive": naive, **{f"LEAR {cw}": ours[cw] for cw in PAPER_WINDOWS}, "LEAR Ens.": ens}
    head = pd.DataFrame({k: scores(real, v) for k, v in models.items()}).T
    out["accuracy"] = head.to_dict(orient="index")
    best_single = min(PAPER_WINDOWS, key=lambda cw: mae(real, ours[cw]))
    gain = {
        "naive_MAE": mae(real, naive),
        "ensemble_MAE": mae(real, ens),
        "ensemble_vs_naive_EUR_MWh": mae(real, naive) - mae(real, ens),
        "ensemble_vs_naive_pct": 100 * (1 - mae(real, ens) / mae(real, naive)),
        "best_single_window": best_single,
        "best_single_MAE": mae(real, ours[best_single]),
        "ensemble_vs_best_single_EUR_MWh": mae(real, ours[best_single]) - mae(real, ens),
        "ensemble_vs_best_single_pct": 100 * (1 - mae(real, ens) / mae(real, ours[best_single])),
        "gw_p_ensemble_better_than_naive": float(gw_test(real, naive, ens)[1]),
        "gw_p_ensemble_better_than_best_single": float(gw_test(real, ours[best_single], ens)[1]),
        "dm_p_ensemble_better_than_naive": float(dm_test(real, naive, ens)[1]),
        "dm_p_ensemble_better_than_best_single": float(dm_test(real, ours[best_single], ens)[1]),
    }
    # Cost of the error on a 1 MW flat position: MAE x hours.
    gain["ensemble_vs_naive_EUR_per_MW_year"] = gain["ensemble_vs_naive_EUR_MWh"] * 24 * 364
    out["headline"] = gain
    md += ["## Accuracy on the test period (728 days)", fmt_table(head, 3), ""]
    md += ["## Headline", "```", json.dumps(gain, indent=1), "```", ""]

    # GW is the test of the paper's results (Lago et al., 2021, §6.2); DM is kept alongside.
    arrays = {k: v.to_numpy() for k, v in models.items()}
    gw = gw_matrix(real.to_numpy(), arrays)
    dm = dm_matrix(real.to_numpy(), arrays)
    out["gw_pvalues"] = gw.to_dict(orient="index")
    out["dm_pvalues"] = dm.to_dict(orient="index")
    md += [
        "## Multivariate GW p-values (H1: column more accurate than row)",
        fmt_table(gw, 4),
        "",
        "## Multivariate DM p-values (H1: column more accurate than row)",
        fmt_table(dm, 4),
        "",
    ]

    # Published results of the paper, quoted next to ours.
    out["published_reference"] = {
        "source": "Lago et al. (2021), published forecasts",
        "MAE": {k: mae(real, pub_daily[k]) for k in ("LEAR Ensemble", "DNN Ensemble")},
    }
    md += [
        "## Published results quoted for reference (MAE)",
        "```",
        json.dumps(out["published_reference"], indent=1),
        "```",
        "",
    ]

    # Our DNNs (published hyperparameters, daily recalibration), with the port check.
    dnn = dnn_block("A", real, ens, naive, missing, published=pub_daily)
    if dnn is not None:
        out["dnn"] = dnn[0]
        port = ROOT / "results" / "dnn" / "port_check.json"  # scripts/check_dnn_port.py
        if port.exists():
            check = json.loads(port.read_text())
            out["dnn"]["port_check"] = {
                "cases": len(check["cases"]),
                "all_ok": check["all_ok"],
                "max_abs_diff": max(c["max_abs_diff"] for c in check["cases"]),
                "tolerance": check["tolerance"],
            }
        md += ["## Phase A: our DNNs", "```", json.dumps(out["dnn"], indent=1), "```", ""]

    out["phase_b"], md_b, frames_b = phase_b(missing)
    md += md_b
    dnn_ens_a = None if dnn is None else dnn[1]
    monthly_figure((real, ens, naive, dnn_ens_a), frames_b)
    # Decision rule: deploy the LEAR ensemble if it beats the naive forecast on the whole
    # phase B test (one-sided multivariate GW, 5 %).
    if out["phase_b"] is not None:
        p_value = out["phase_b"]["accuracy"]["GW p (ens. better than naive)"]
        out["decision"] = {
            "rule": "LEAR ensemble if one-sided GW p < 0.05 vs naive on the phase B test",
            "gw_p": p_value,
            "dm_p": out["phase_b"]["accuracy"]["DM p (ens. better than naive)"],
            "deployed_model": "lear_ensemble" if p_value < 0.05 else "naive",
            "recalibration": "daily, four windows (56, 84, 1092, 1456 days)",
            "fallback": "naive forecast when a day has no LEAR forecast",
        }
        md += ["## Decision", "```", json.dumps(out["decision"], indent=1), "```", ""]
    # Cost of forecasting hours on 15-minute products: the error a perfect hourly forecast
    # would still make against the quarter-hour prices (raw ENTSO-E prices, from the cache).
    try:
        raw = EntsoeSource().raw("Price")
    except RuntimeError:  # cache missing and no API key
        missing.append("ENTSO-E price cache (run build_phase_b.py)")
    else:
        lo = pd.Timestamp(QUARTER_HOUR_START, tz=TZ)
        hi = pd.Timestamp(PHASE_B_TEST[1], tz=TZ) + pd.Timedelta(days=1)
        gap, hours = intra_hour_deviation(raw[(raw.index >= lo) & (raw.index < hi)])
        out["quarter_hour"] = {
            "period": [QUARTER_HOUR_START, PHASE_B_TEST[1]],
            "hours": hours,
            "perfect_hourly_forecast_MAE": gap,
        }
        md += [
            "## Quarter-hour products: error of a perfect hourly forecast",
            "```",
            json.dumps(out["quarter_hour"], indent=1),
            "```",
            "",
        ]
    if missing:
        md.append(f"Missing experiments: {sorted(set(missing))}")
    out["missing"] = sorted(set(missing))
    # Written by scripts/build_phase_b.py and scripts/compare_sources.py.
    for key in ("data_report", "source_comparison"):
        path = ROOT / "results" / f"{key}.json"
        if path.exists():
            out[key] = json.loads(path.read_text())
    (ROOT / "results" / "summary.md").write_text("\n".join(md) + "\n")
    (ROOT / "results" / "metrics.json").write_text(json.dumps(out, indent=1, default=float))
    # README: the template with every number read back from metrics.json.
    metrics = json.loads((ROOT / "results" / "metrics.json").read_text())
    template = (ROOT / "docs" / "README.template.md").read_text()
    (ROOT / "README.md").write_text(render(template, metrics))
    print("\n".join(md))


if __name__ == "__main__":
    main()
