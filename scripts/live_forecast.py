"""Forecast the next Belgian delivery day with the LEAR and DNN ensembles; publish in live/.

Run every evening by .github/workflows/live.yml, after the French day-ahead generation
forecast of the next day is published on ENTSO-E (deadline 18:00 Brussels time, so after
the 12:00 gate closure of the auction: the forecasts use the information of the paper but
cannot be used to bid); needs ENTSOE_API_KEY. Steps: extend the cached ENTSO-E series,
forecast the delivery day with the LEAR ensemble and with the DNN ensemble (the four DNNs
recalibrated in parallel, as in the backtests), append them to
results/forecasts/live/forecasts.csv and dnn_forecasts.csv (the training record of each DNN
to results/dnn/live/summary.csv; weights are not kept) and write the page live/README.md
(with live/forecast.png). The two models are shown side by side, never averaged. When
an input is not published yet, no forecast is written and the page says so. A day already
forecast is not forecast again (the workflow runs twice, the second time as a fallback).
Then the forecasts of today (made the evening before) are compared with today's realised
prices, taken from SMARD.de (CC BY 4.0; the ENTSO-E prices are not on its free re-use
list): quarter-hour prices and their hourly mean, the naive forecast, LEAR and DNN on one
chart (live/compare.png), and the MAE of each against the hourly mean appended to
results/forecasts/live/scores.csv.
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
from be_power_forecast.data.calendar import intra_hour_deviation, to_local_days
from be_power_forecast.data.smard import ATTRIBUTION, smard_prices
from be_power_forecast.data.sources import EntsoeSource
from be_power_forecast.evaluation.metrics import naive_source_day
from be_power_forecast.live import forecast_day, live_frame, update_raw
from be_power_forecast.models import dnn
from be_power_forecast.models.lear import ensemble

LIVE = RESULTS_DIR / "forecasts" / "live"
PAGE = REPO_ROOT / "live"
ELIA = "https://www.elia.be/en/grid-data/transmission/day-ahead-reference-price"
# Reference palette (dataviz skill, light mode): categorical slots 1-3, neutral ink and grey.
BLUE, ORANGE, AQUA, INK, GREY = "#2a78d6", "#eb6834", "#1baf7a", "#52514e", "#8a8984"
SCORED_DAYS = 10  # live days scored again at each run (late or missed runs)


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


def stored(path, day: pd.Timestamp):
    if not path.exists():
        return None
    old = pd.read_csv(path, index_col=0, parse_dates=True)
    return old.loc[day, HOURS].to_numpy(float) if day in old.index else None


def compare(today: pd.Timestamp, get=None) -> dict | None:
    """Realised prices of ``today`` (SMARD) with the naive, LEAR and DNN forecasts of it, and
    the scores of the recent live days; ``None`` when today's prices are not complete."""
    lo = (today - pd.Timedelta(days=SCORED_DAYS + 7)).tz_localize(TZ).tz_convert("UTC")
    hi = (today + pd.Timedelta(days=1)).tz_localize(TZ).tz_convert("UTC")
    quarter = smard_prices(lo, hi, **({"get": get} if get else {}))
    if quarter.empty:
        return None
    daily = to_local_days(quarter)[0]
    lear = pd.read_csv(LIVE / "forecasts.csv", index_col=0, parse_dates=True)
    dnn_path = LIVE / "dnn_forecasts.csv"
    dnn_fc = pd.read_csv(dnn_path, index_col=0, parse_dates=True) if dnn_path.exists() else None
    path = LIVE / "scores.csv"
    scores = pd.read_csv(path, index_col=0, parse_dates=True) if path.exists() else pd.DataFrame()
    for day in lear.index[lear.index > today - pd.Timedelta(days=SCORED_DAYS)]:
        if day > today or day not in daily.index or naive_source_day(day) not in daily.index:
            continue
        real, naive = daily.loc[day].to_numpy(), daily.loc[naive_source_day(day)].to_numpy()
        if not (np.isfinite(real).all() and np.isfinite(naive).all()):
            continue
        local = quarter.tz_convert(TZ)
        inside = (local.index >= day.tz_localize(TZ)) & (
            local.index < (day + pd.Timedelta(days=1)).tz_localize(TZ)
        )
        row = {
            "MAE naive": float(np.mean(np.abs(real - naive))),
            "MAE LEAR": float(np.mean(np.abs(real - lear.loc[day, HOURS].to_numpy(float)))),
            "MAE DNN": float(np.mean(np.abs(real - dnn_fc.loc[day, HOURS].to_numpy(float))))
            if dnn_fc is not None and day in dnn_fc.index
            else np.nan,
            "MAE perfect hourly vs quarter-hours": intra_hour_deviation(quarter[inside])[0],
        }
        scores = pd.concat(
            [
                scores.drop(index=day, errors="ignore"),
                pd.DataFrame([row], pd.DatetimeIndex([day], name="Date")),
            ]
        )
    if len(scores):
        scores.sort_index().to_csv(path, float_format="%.3f")
    if today not in scores.index:
        return None
    local = quarter.tz_convert(TZ)
    q = local[
        (local.index >= today.tz_localize(TZ))
        & (local.index < (today + pd.Timedelta(days=1)).tz_localize(TZ))
    ]
    return {
        "quarter": q,
        "real": daily.loc[today].to_numpy(),
        "naive": daily.loc[naive_source_day(today)].to_numpy(),
        "lear": stored(LIVE / "forecasts.csv", today),
        "dnn": stored(dnn_path, today),
        "scores": scores.sort_index(),
    }


def compare_chart(today: pd.Timestamp, c: dict) -> None:
    fig, ax = plt.subplots(figsize=(7.5, 3.4), dpi=150)
    q = c["quarter"]
    x = (q.index.hour + q.index.minute / 60).to_numpy()
    ax.step(
        [*x, 24],
        [*q.to_numpy(), q.iloc[-1]],
        where="post",
        color=GREY,
        lw=0.8,
        label="Realised, quarter-hours",
    )
    for key, color, lw, label in [
        ("real", INK, 2.2, "Realised, hourly mean"),
        ("naive", ORANGE, 1.6, "Naive"),
        ("lear", BLUE, 1.6, "LEAR"),
        ("dnn", AQUA, 1.6, "DNN"),
    ]:
        v = c[key]
        if v is not None:
            ax.step(range(25), [*v, v[-1]], where="post", color=color, lw=lw, label=label)
    ax.set_xticks(range(0, 25, 3))
    ax.set_xlabel("Hour (Brussels time)", color=INK)
    ax.set_ylabel("EUR/MWh", color=INK)
    ax.set_title(f"{today.date()}: forecasts vs realised prices", color=INK, fontsize=10)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.grid(axis="y", color="#e4e3df")
    ax.legend(frameon=False, fontsize=7, ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.22))
    fig.tight_layout()
    fig.savefig(PAGE / "compare.png")
    plt.close(fig)


def compare_section(today: pd.Timestamp, c: dict | None) -> list[str]:
    (PAGE / "compare.png").unlink(missing_ok=True)
    md = [f"## Today, {today.date()}: forecasts vs realised prices", ""]
    if c is None:
        return md + [
            "Not available: no live forecast of today, or its prices are not complete.",
            "",
        ]
    compare_chart(today, c)
    s = c["scores"]
    last = s.loc[today]
    # Last 30 days: only days scored for the three forecasts, so that the means compare.
    both = s[s.index > today - pd.Timedelta(days=30)].dropna()
    fmt = lambda v: "–" if pd.isna(v) else f"{v:.2f}"  # noqa: E731
    md += [
        "![Forecasts vs realised prices](compare.png)",
        "",
        "Forecasts made the evening before (after the auction, with the information of the "
        "paper). MAE in EUR/MWh against the hourly mean of the realised prices.",
        "",
        "| | Naive | LEAR | DNN | Perfect hourly forecast |",
        "|---|---|---|---|---|",
        f"| {today.date()} | {fmt(last['MAE naive'])} | {fmt(last['MAE LEAR'])} | "
        f"{fmt(last['MAE DNN'])} | {fmt(last['MAE perfect hourly vs quarter-hours'])}* |",
        f"| Last 30 days, mean of {len(both)} days with the three forecasts | "
        f"{fmt(both['MAE naive'].mean())} | {fmt(both['MAE LEAR'].mean())} | "
        f"{fmt(both['MAE DNN'].mean())} | "
        f"{fmt(both['MAE perfect hourly vs quarter-hours'].mean())}* |",
        "",
        f"DNN more accurate than LEAR on {int((both['MAE DNN'] < both['MAE LEAR']).sum())} of "
        f"these {len(both)} days. *Against the quarter-hour prices: the error a "
        "perfect hourly forecast still makes, since the models forecast hours.",
        "",
        f"Realised prices: {ATTRIBUTION} (www.smard.de), equal to the ENTSO-E prices.",
        "",
    ]
    return md


def write_page(day, values, dnn_values, reason: str, now, comparison: list[str]) -> None:
    PAGE.mkdir(exist_ok=True)
    md = [
        "# Live forecast of the Belgian day-ahead price",
        "",
        f"Updated automatically on {now:%Y-%m-%d %H:%M} (Brussels time) by "
        "`scripts/live_forecast.py`, every evening once the French day-ahead generation "
        "forecast of the next day is published on ENTSO-E (by 18:00, after the 12:00 "
        "auction: these forecasts use the information of the paper but could not be used "
        "to bid). Two models of the backtests, recalibrated every day and shown side by side "
        "(not averaged): the 4-window LEAR ensemble and the ensemble of the four DNNs of "
        "Lago et al. (2021).",
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
    md += ["", *comparison]
    md += [
        f"Official prices: [Elia]({ELIA}) and the "
        "[ENTSO-E Transparency Platform](https://transparency.entsoe.eu/).",
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

    values, dnn_values = (
        stored(LIVE / "forecasts.csv", day),
        stored(LIVE / "dnn_forecasts.csv", day),
    )
    records, reason = [], ""
    if values is not None and dnn_values is not None and not args.day:
        print(f"{day.date()}: already forecast")
    else:
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
    if records:
        append(LIVE / "dnn_forecasts.csv", day, dnn_values)
        path = RESULTS_DIR / "dnn" / "live" / "summary.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        old = pd.read_csv(path) if path.exists() else pd.DataFrame()
        new = pd.DataFrame(records)
        if len(old):
            old = old[~((old["date"] == str(day.date())) & old["dnn"].isin(new["dnn"]))]
        pd.concat([old, new]).to_csv(path, index=False)
    today = day - pd.Timedelta(days=1)
    try:
        comparison = compare(today) if (LIVE / "forecasts.csv").exists() else None
    except OSError as err:  # SMARD unreachable: the forecast is still published
        print(f"no comparison: {err}")
        comparison = None
    PAGE.mkdir(exist_ok=True)
    write_page(day, values, dnn_values, reason, now, compare_section(today, comparison))


if __name__ == "__main__":
    main()
