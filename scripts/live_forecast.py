"""Forecast the next Belgian delivery day with the LEAR and DNN ensembles; publish in live/.

Run every morning by .github/workflows/live.yml, before the 12:00 (Brussels) gate closure
of the day-ahead auction; needs ENTSOE_API_KEY. Steps: extend the cached ENTSO-E series,
forecast the delivery day with the LEAR ensemble and with the DNN ensemble (the four DNNs
recalibrated in parallel, as in the backtests), append them to
results/forecasts/live/forecasts.csv and dnn_forecasts.csv (the training record of each DNN
to results/dnn/live/summary.csv; weights are not kept) and write the page live/README.md
(with live/forecast.png). The two models are shown side by side, never averaged. When
an input is not published yet, no forecast is written and the page says so: the naive
forecast is a copy of past prices, which are never published (ENTSO-E re-use terms).
Usage: python scripts/live_forecast.py [--day YYYY-MM-DD]
"""

from __future__ import annotations

import argparse
import multiprocessing as mp
import time
from concurrent.futures import ProcessPoolExecutor

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from run_dnn import _init_worker, environment

from be_power_forecast.backtest import HOURS
from be_power_forecast.config import EXOGENOUS, REPO_ROOT, RESULTS_DIR, TZ
from be_power_forecast.data.sources import EntsoeSource
from be_power_forecast.live import forecast_day, live_frame, update_raw
from be_power_forecast.models import dnn
from be_power_forecast.models.lear import ensemble

LIVE = RESULTS_DIR / "forecasts" / "live"
PAGE = REPO_ROOT / "live"
ELIA = "https://www.elia.be/en/grid-data/transmission/day-ahead-reference-price"
BLUE, AQUA, INK = "#2a78d6", "#1baf7a", "#52514e"


def _dnn_job(job):
    frame, day, name = job
    inputs = dnn.HourlyInputs.from_frame(frame)
    t = int(np.flatnonzero(inputs.dates == day)[0])
    start = time.time()
    try:
        values, record, _ = dnn.forecast_day(inputs, t, dnn.load_hyperparameters()[name])
    except ValueError:  # an input of the day is missing
        return name, None, None
    record = {"dnn": name, **record, "seconds": round(time.time() - start, 1)}
    record.pop("history")
    record.pop("forecast")
    return name, values, {**record, **environment()}


def dnn_forecast(frame: pd.DataFrame, day: pd.Timestamp):
    """DNN ensemble of ``day`` and the training records, or ``(None, [])`` if an input is
    missing. The four DNNs train in parallel, one deterministic thread each."""
    jobs = [(frame, day, name) for name in dnn.load_hyperparameters()]
    context = mp.get_context("spawn")
    with ProcessPoolExecutor(len(jobs), mp_context=context, initializer=_init_worker) as pool:
        results = list(pool.map(_dnn_job, jobs))
    if any(values is None for _, values, _ in results):
        return None, []
    return ensemble([values for _, values, _ in results]), [r for *_, r in results]


def append(path, day: pd.Timestamp, values: np.ndarray) -> None:
    old = pd.read_csv(path, index_col=0, parse_dates=True) if path.exists() else pd.DataFrame()
    row = pd.DataFrame([values], pd.DatetimeIndex([day], name="Date"), HOURS)
    pd.concat([old.drop(index=day, errors="ignore"), row]).sort_index().to_csv(
        path, float_format="%.6f"
    )


def write_page(day, values, dnn_values, reason: str, now) -> None:
    PAGE.mkdir(exist_ok=True)
    md = [
        "# Live forecast of the Belgian day-ahead price",
        "",
        f"Updated automatically on {now:%Y-%m-%d %H:%M} (Brussels time) by "
        "`scripts/live_forecast.py`, every morning before the 12:00 gate closure of the "
        "day-ahead auction. Two models of the backtests, recalibrated every morning and "
        "shown side by side (not averaged): the 4-window LEAR ensemble and the ensemble of "
        "the four DNNs of Lago et al. (2021).",
        "",
        f"## Delivery day {day.date()}",
        "",
    ]
    (PAGE / "forecast.png").unlink(missing_ok=True)
    if values is None:
        md.append(f"No forecast for this day: {reason}.")
    else:
        fig, ax = plt.subplots(figsize=(7, 3), dpi=150)
        ax.step(range(25), [*values, values[-1]], where="post", color=BLUE, lw=2, label="LEAR")
        if dnn_values is not None:
            ax.step(
                range(25),
                [*dnn_values, dnn_values[-1]],
                where="post",
                color=AQUA,
                lw=2,
                label="DNN",
            )
            ax.legend(frameon=False, fontsize=8)
        ax.set_xticks(range(0, 25, 3))
        ax.set_xlabel("Hour (Brussels time)", color=INK)
        ax.set_ylabel("EUR/MWh", color=INK)
        ax.set_title(f"Forecasts for {day.date()}", color=INK, fontsize=10)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        ax.grid(axis="y", color="#e4e3df")
        fig.tight_layout()
        fig.savefig(PAGE / "forecast.png")
        plt.close(fig)
        rows = [("LEAR", values)] + ([("DNN", dnn_values)] if dnn_values is not None else [])
        md += ["![Forecast](forecast.png)", ""]
        for hours in (range(12), range(12, 24)):
            md += [
                "| Hour (EUR/MWh) | " + " | ".join(f"{h:02d}" for h in hours) + " |",
                "|---" * 13 + "|",
            ]
            md += [f"| {n} | " + " | ".join(f"{v[h]:.1f}" for h in hours) + " |" for n, v in rows]
            md.append("")
        if dnn_values is None:
            md += ["No DNN forecast for this day: an input of its days is missing.", ""]
        md += [
            "Hourly prices; since 1 October 2025 each value is the average of four quarter-hours.",
        ]
    md += [
        "",
        "The official prices of this day are published after the 12:00 auction, around "
        f"13:00, by [Elia]({ELIA}) and the "
        "[ENTSO-E Transparency Platform](https://transparency.entsoe.eu/); they are not "
        "reproduced here (ENTSO-E re-use terms).",
        "",
    ]
    (PAGE / "README.md").write_text("\n".join(md))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--day", help="delivery day (default: tomorrow, Brussels time)")
    args = parser.parse_args()
    now = pd.Timestamp.now(tz=TZ)
    tomorrow = now.tz_localize(None).normalize() + pd.Timedelta(days=1)
    day = pd.Timestamp(args.day) if args.day else tomorrow

    source = EntsoeSource()
    raw = {name: update_raw(source, name, day) for name in source.columns}
    frame = live_frame(raw, day)
    values = forecast_day(frame, day)
    dnn_values, records = dnn_forecast(frame, day) if values is not None else (None, [])
    end = (day + pd.Timedelta(days=1)).tz_localize(TZ)
    unpublished = [n for n in EXOGENOUS if raw[n].index[-1] + pd.Timedelta(hours=1) < end]
    reason = (
        f"{' and '.join(unpublished)} not published yet"
        if unpublished
        else "an input of the previous days is missing"
    )
    print(
        f"{day.date()}: "
        + ("LEAR ensemble" if values is not None else reason)
        + (", DNN ensemble" if dnn_values is not None else "")
    )
    if values is not None:
        LIVE.mkdir(parents=True, exist_ok=True)
        append(LIVE / "forecasts.csv", day, values)
    if dnn_values is not None:
        append(LIVE / "dnn_forecasts.csv", day, dnn_values)
        path = RESULTS_DIR / "dnn" / "live" / "summary.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        old = pd.read_csv(path) if path.exists() else pd.DataFrame()
        new = pd.DataFrame(records)
        if len(old):
            old = old[~((old["date"] == str(day.date())) & old["dnn"].isin(new["dnn"]))]
        pd.concat([old, new]).to_csv(path, index=False)
    write_page(day, values, dnn_values, reason, now)


if __name__ == "__main__":
    main()
