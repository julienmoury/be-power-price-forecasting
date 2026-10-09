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
from be_power_forecast.data.sources import (
    BE_TEST_BEGIN,
    BE_TEST_END,
    EpftoolboxZenodoSource,
)
from be_power_forecast.evaluation.dm import dm_matrix, dm_test
from be_power_forecast.evaluation.metrics import mae, naive_forecast, rmae, rmse, smape
from be_power_forecast.models.lear import ensemble

ROOT = Path(__file__).resolve().parents[1]
FC = ROOT / "results" / "forecasts"
FIG = ROOT / "results" / "figures"
PUBLISHED = ROOT / "tests" / "reference" / "Forecasts_BE_DNN_LEAR_ensembles.csv"

PAPER_WINDOWS = [56, 84, 1092, 1456]
ALL_WINDOWS = [28, 56, 84, 182, 364, 728, 1092, 1456]
ABLATIONS = {
    "no_load_fr": "without FR load forecast",
    "no_gen_fr": "without FR generation forecast",
    "no_exog": "without any exogenous input",
}

# Reference palette (dataviz skill, light mode): categorical slots 1-3 + neutral ink.
BLUE, ORANGE, AQUA, GREY, INK = "#2a78d6", "#eb6834", "#1baf7a", "#8a8984", "#52514e"


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


def main() -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    df = EpftoolboxZenodoSource("BE").load()
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

    ours = {cw: load(f"lear_cw{cw}") for cw in ALL_WINDOWS}
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
            "mean |ours - published|": mae(pub_daily[f"LEAR {cw}"], ours[cw]),
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
            "mean |ours - published|": mae(pub_daily["LEAR Ensemble"], ens),
        }
    for cw in (56, 84):
        f = load(f"lear_exoglags12_cw{cw}")
        if f is None:
            missing.append(f"lear_exoglags12_cw{cw}")
            continue
        rows[f"LEAR {cw}, exog. lags D-1/D-2 (pre-2024 library)"] = {
            "MAE (ours)": mae(real, f),
            "MAE (published)": mae(real, pub_daily[f"LEAR {cw}"]),
            "sMAPE % (ours)": 100 * smape(real, f),
            "sMAPE % (published)": 100 * smape(real, pub_daily[f"LEAR {cw}"]),
            "mean |ours - published|": mae(pub_daily[f"LEAR {cw}"], f),
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
        "dm_p_ensemble_better_than_naive": float(dm_test(real, naive, ens)[1]),
        "dm_p_ensemble_better_than_best_single": float(dm_test(real, ours[best_single], ens)[1]),
    }
    # Cost of the error on a 1 MW flat position: MAE x hours.
    gain["ensemble_vs_naive_EUR_per_MW_year"] = gain["ensemble_vs_naive_EUR_MWh"] * 24 * 364
    out["headline"] = gain
    md += ["## Accuracy on the test period (728 days)", fmt_table(head, 3), ""]
    md += ["## Headline", "```", json.dumps(gain, indent=1), "```", ""]

    dm = dm_matrix(real.to_numpy(), {k: v.to_numpy() for k, v in models.items()})
    out["dm_pvalues"] = dm.to_dict(orient="index")
    md += [
        "## Multivariate DM p-values (H1: column more accurate than row)",
        fmt_table(dm, 4),
        "",
    ]

    # ---- 3. Robustness: calibration window -------------------------------------------------
    win = pd.DataFrame(
        {
            cw: {"MAE": mae(real, ours[cw]), "rMAE": rmae(real, ours[cw])}
            for cw in ALL_WINDOWS
            if ours[cw] is not None
        }
    ).T
    win.index.name = "window (days)"
    out["calibration_windows"] = win.to_dict(orient="index")
    md += ["## Calibration window", fmt_table(win, 3), ""]

    # ---- 4. Robustness: inputs removed --------------------------------------------------------
    abl_rows = {"all inputs (baseline)": {"MAE ensemble": mae(real, ens)}}
    for name, label in ABLATIONS.items():
        fcs = [load(f"lear_{name}_cw{cw}") for cw in PAPER_WINDOWS]
        if any(f is None for f in fcs):
            missing.append(f"lear_{name}_*")
            continue
        e = pd.DataFrame(
            ensemble([f.to_numpy() for f in fcs]), index=real.index, columns=real.columns
        )
        row = {"MAE ensemble": mae(real, e)}
        for cw, f in zip(PAPER_WINDOWS, fcs, strict=True):
            row[f"MAE {cw}"] = mae(real, f)
        row["delta vs baseline"] = mae(real, e) - mae(real, ens)
        row["DM p (baseline better)"] = float(dm_test(real, e, ens)[1])
        abl_rows[label] = row
    for cw in PAPER_WINDOWS:
        abl_rows["all inputs (baseline)"][f"MAE {cw}"] = mae(real, ours[cw])
    abl = pd.DataFrame(abl_rows).T
    out["ablations"] = abl.to_dict(orient="index")
    md += ["## Inputs removed (ensemble of the 4 windows)", fmt_table(abl, 3), ""]

    # ---- 5. Robustness: sub-periods ------------------------------------------------------------
    daily_max = real.max(axis=1)
    spike_threshold = float(daily_max.quantile(0.95))
    peak_hours = [f"h{h}" for h in range(8, 20)]
    weekday = real.index.dayofweek < 5
    masks = {
        "2015": real.index.year == 2015,
        "2016": real.index.year == 2016,
        "Q4 2016 (FR nuclear inspections)": real.index >= "2016-10-01",
        "Jan-Sep 2016": (real.index.year == 2016) & (real.index < "2016-10-01"),
        f"spike days (daily max > {spike_threshold:.0f})": (daily_max > spike_threshold).to_numpy(),
        "other days": (daily_max <= spike_threshold).to_numpy(),
    }
    sub_rows = {}
    for label, m in masks.items():
        r, n_, e = real[m], naive[m], ens[m]
        sub_rows[label] = {
            "days": int(m.sum()),
            "mean price": float(r.to_numpy().mean()),
            "MAE naive": mae(r, n_),
            "MAE LEAR ens.": mae(r, e),
            "gain %": 100 * (1 - mae(r, e) / mae(r, n_)),
            **{f"MAE {cw}": mae(r, ours[cw][m]) for cw in PAPER_WINDOWS},
            "DM p (ens. better than naive)": float(dm_test(r, n_, e)[1]),
        }
    # Peak / off-peak on weekdays (hour columns, not days)
    for label, cols in {
        "weekday peak 08-20h": peak_hours,
        "weekday off-peak": [c for c in real.columns if c not in peak_hours],
    }.items():
        r, n_, e = real.loc[weekday, cols], naive.loc[weekday, cols], ens.loc[weekday, cols]
        sub_rows[label] = {
            "days": int(weekday.sum()),
            "mean price": float(r.to_numpy().mean()),
            "MAE naive": mae(r, n_),
            "MAE LEAR ens.": mae(r, e),
            "gain %": 100 * (1 - mae(r, e) / mae(r, n_)),
            **{f"MAE {cw}": mae(r, ours[cw].loc[weekday, cols]) for cw in PAPER_WINDOWS},
            "DM p (ens. better than naive)": float(dm_test(r, n_, e)[1]),
        }
    sub = pd.DataFrame(sub_rows).T
    out["subperiods"] = sub.to_dict(orient="index")
    md += ["## Sub-periods", fmt_table(sub, 3), ""]

    # ---- Figures ---------------------------------------------------------------------------
    # Fig 1: MAE vs calibration window, with ensemble and naive as reference lines.
    fig, ax = plt.subplots(figsize=(7, 3.6), dpi=150)
    style(ax)
    ax.plot(win.index, win["MAE"], color=BLUE, lw=2, marker="o", ms=6, label="LEAR, single window")
    ax.axhline(mae(real, ens), color=AQUA, lw=2, ls="--", label="LEAR ensemble (56/84/1092/1456)")
    ax.axhline(mae(real, naive), color=ORANGE, lw=2, ls=":", label="Naive benchmark")
    ax.set_xscale("log")
    ax.set_xticks(win.index)
    ax.set_xticklabels(win.index)
    ax.set_xlabel("Calibration window (days, log scale)", color=INK)
    ax.set_ylabel("MAE (EUR/MWh)", color=INK)
    ax.set_title(
        "Belgian day-ahead, 2015-2016: error vs calibration window", color=INK, fontsize=10
    )
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG / "mae_vs_window.png")
    plt.close(fig)

    # Fig 2: monthly MAE, naive vs LEAR ensemble.
    abs_n = (real - naive).abs().mean(axis=1).resample("MS").mean()
    abs_e = (real - ens).abs().mean(axis=1).resample("MS").mean()
    fig, ax = plt.subplots(figsize=(7, 3.6), dpi=150)
    style(ax)
    ax.plot(abs_n.index, abs_n, color=ORANGE, lw=2, label="Naive benchmark")
    ax.plot(abs_e.index, abs_e, color=BLUE, lw=2, label="LEAR ensemble")
    ax.set_ylabel("Monthly MAE (EUR/MWh)", color=INK)
    ax.set_title("Where the models break: monthly error, test period", color=INK, fontsize=10)
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG / "monthly_mae.png")
    plt.close(fig)

    # Fig 3: ablations (ensemble MAE), horizontal bars.
    labels = list(abl.index)[::-1]
    values = abl["MAE ensemble"].to_numpy()[::-1]
    fig, ax = plt.subplots(figsize=(7, 2.8), dpi=150)
    style(ax)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", color="#e4e3df", linewidth=0.8)
    colors = [BLUE if lab.startswith("all inputs") else GREY for lab in labels]
    ax.barh(labels, values, color=colors, height=0.6, edgecolor="white", linewidth=2)
    for y, v in enumerate(values):
        ax.text(v + 0.05, y, f"{v:.2f}", va="center", fontsize=8, color=INK)
    naive_mae = mae(real, naive)
    ax.axvline(naive_mae, color=ORANGE, lw=2, ls=":")
    ax.text(
        naive_mae - 0.1,
        len(labels) - 0.45,
        f"naive {naive_mae:.2f}",
        ha="right",
        va="bottom",
        fontsize=8,
        color=INK,
    )
    ax.set_ylim(-0.5, len(labels) - 0.1)
    ax.set_xlabel("MAE of the LEAR ensemble (EUR/MWh)", color=INK)
    ax.set_title("Value of the French fundamentals", color=INK, fontsize=10, pad=14)
    fig.tight_layout()
    fig.savefig(FIG / "ablations.png")
    plt.close(fig)

    if missing:
        md.append(f"Missing experiments: {sorted(set(missing))}")
    out["missing"] = sorted(set(missing))
    data_report = ROOT / "results" / "data_report.json"  # written by build_phase_b.py
    if data_report.exists():
        out["data_report"] = json.loads(data_report.read_text())
    (ROOT / "results" / "summary.md").write_text("\n".join(md) + "\n")
    (ROOT / "results" / "metrics.json").write_text(json.dumps(out, indent=1, default=float))
    print("\n".join(md))


if __name__ == "__main__":
    main()
