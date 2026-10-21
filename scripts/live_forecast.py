"""Forecast the next Belgian delivery day with the LEAR and DNN ensembles; publish in live/.

Run every evening by .github/workflows/live.yml, after the French day-ahead generation
forecast of the next day is published on ENTSO-E (deadline 18:00 Brussels time, so after
the 12:00 gate closure of the auction: the forecasts use the information of the paper but
cannot be used to bid); needs ENTSOE_API_KEY. Steps: extend the cached ENTSO-E series,
forecast the delivery day with the LEAR ensemble and with the DNN ensemble (the four DNNs
recalibrated in parallel, as in the backtests), append them to
results/forecasts/live/forecasts.csv and dnn_forecasts.csv (the training record of each DNN
to results/dnn/live/summary.csv; weights are not kept), for the API and the next day
(LEAR and DNN are never averaged). When an input is not published yet, no forecast is
written. A model that already has a forecast of the day is not run again (the workflow
runs twice, the second time as a fallback; ``--day`` fills a missing past day).

The realised prices come from SMARD.de (CC BY 4.0; the ENTSO-E prices are not on its free
re-use list); their hourly means since the first live day are kept in
results/live/realised.csv. The page live/README.md shows today's forecasts against today's
prices (live/compare.png) and the errors of each model since the first live day, computed
in SQL (be_power_forecast.live_report).
Usage: python scripts/live_forecast.py [--day YYYY-MM-DD] [--page-only]
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
from be_power_forecast.config import EXOGENOUS, LIVE_START, REPO_ROOT, RESULTS_DIR, TZ
from be_power_forecast.data.calendar import intra_hour_deviation, to_local_days
from be_power_forecast.data.smard import ATTRIBUTION, smard_prices
from be_power_forecast.data.sources import EntsoeSource
from be_power_forecast.evaluation.metrics import naive_source_day
from be_power_forecast.live import forecast_day, live_frame, update_raw
from be_power_forecast.live_report import live_errors
from be_power_forecast.models import dnn
from be_power_forecast.models.lear import ensemble

LIVE = RESULTS_DIR / "forecasts" / "live"
REALISED = RESULTS_DIR / "live" / "realised.csv"
PAGE = REPO_ROOT / "live"
ELIA = "https://www.elia.be/en/grid-data/transmission/day-ahead-reference-price"
# Reference palette (dataviz skill, light mode): categorical slots 1-3, neutral ink and grey.
BLUE, ORANGE, AQUA, INK, GREY = "#2a78d6", "#eb6834", "#1baf7a", "#52514e", "#8a8984"


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


def update_realised(today: pd.Timestamp, get=None) -> None:
    """Hourly means of the realised prices (SMARD) from a week before the first live day
    (the naive forecast copies up to 7 days back) to ``today``, complete days only."""
    first = pd.Timestamp(LIVE_START) - pd.Timedelta(days=7)
    lo = first.tz_localize(TZ).tz_convert("UTC")
    hi = (today + pd.Timedelta(days=1)).tz_localize(TZ).tz_convert("UTC")
    daily = to_local_days(smard_prices(lo, hi, **({"get": get} if get else {})))[0]
    daily = daily[np.isfinite(daily.to_numpy()).all(axis=1)]
    daily.columns, daily.index.name = HOURS, "Date"
    REALISED.parent.mkdir(parents=True, exist_ok=True)
    daily.loc[first:today].to_csv(REALISED, float_format="%.2f")


def compare(today: pd.Timestamp, get=None) -> dict | None:
    """Realised prices of ``today`` (SMARD) with the naive, LEAR and DNN forecasts of it;
    ``None`` when there is no LEAR forecast of today or its prices are not complete."""
    lear = stored(LIVE / "forecasts.csv", today)
    if lear is None:
        return None
    source = naive_source_day(today)
    lo = source.tz_localize(TZ).tz_convert("UTC")
    hi = (today + pd.Timedelta(days=1)).tz_localize(TZ).tz_convert("UTC")
    quarter = smard_prices(lo, hi, **({"get": get} if get else {}))
    if quarter.empty:
        return None
    daily = to_local_days(quarter)[0]
    if today not in daily.index or source not in daily.index:
        return None
    real, naive = daily.loc[today].to_numpy(), daily.loc[source].to_numpy()
    if not (np.isfinite(real).all() and np.isfinite(naive).all()):
        return None
    q = quarter[quarter.index >= today.tz_localize(TZ)]
    forecasts = {"naive": naive, "lear": lear, "dnn": stored(LIVE / "dnn_forecasts.csv", today)}
    mae = {k: None if v is None else float(np.mean(np.abs(real - v))) for k, v in forecasts.items()}
    mae["perfect"] = intra_hour_deviation(q)[0]
    return {"quarter": q.tz_convert(TZ), "real": real, **forecasts, "mae": mae}


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


def table(frame: pd.DataFrame, first: str) -> list[str]:
    """Markdown rows of a daily or by-hour error table (EUR/MWh)."""
    fmt = lambda v: "–" if pd.isna(v) else f"{v:.2f}"  # noqa: E731
    rows = [f"| {first} | Naive | LEAR | DNN |", "|---|---|---|---|"]
    for _, r in frame.iterrows():
        key = r.iloc[0]
        key = f"{key:%Y-%m-%d}" if hasattr(key, "strftime") else f"{key:.0f}"
        rows.append(f"| {key} | {fmt(r.naive)} | {fmt(r.lear)} | {fmt(r.dnn)} |")
    return rows


def write_page(today: pd.Timestamp, c: dict | None, report: dict | None, now) -> None:
    """The live page: today's forecasts against today's prices, then every day since the
    first live day."""
    PAGE.mkdir(exist_ok=True)
    (PAGE / "compare.png").unlink(missing_ok=True)
    start = pd.Timestamp(LIVE_START)
    md = [
        "# Live: Belgian day-ahead prices",
        "",
        f"Since {start:%-d %B %Y}, the day after the end of the backtest, the two models "
        "of the project forecast every Belgian delivery day: the LEAR ensemble and the DNN "
        "ensemble, retrained every evening exactly as in the backtest. Each forecast is "
        "then compared with the realised prices.",
        "",
        "The forecasts use the French generation forecast, which is published after the "
        "12:00 auction: they follow the paper, but could not have been used to bid.",
        "",
        f"Updated on {now:%Y-%m-%d}.",
        "",
        f"## Today, {today.date()}",
        "",
    ]
    if c is None:
        md += ["Not available yet: no forecast of today, or its prices are not complete.", ""]
    else:
        compare_chart(today, c)
        m = c["mae"]
        fmt = lambda v: "–" if v is None else f"{v:.2f}"  # noqa: E731
        md += [
            "![Forecasts vs realised prices](compare.png)",
            "",
            "Error (MAE, EUR/MWh) against the hourly mean of the realised prices:",
            "",
            "| Naive | LEAR | DNN | Perfect hourly forecast* |",
            "|---|---|---|---|",
            f"| {fmt(m['naive'])} | {fmt(m['lear'])} | {fmt(m['dnn'])} | {fmt(m['perfect'])} |",
            "",
            "*Against the quarter-hour prices: the error a perfect hourly forecast still "
            "makes, since the models forecast hours.",
            "",
        ]
    if report is not None and len(report["summary"]):
        s = report["summary"].set_index("model")
        days = int(s["days"].max())
        names = {"naive": "Naive", "lear": "LEAR", "dnn": "DNN"}
        md += [
            f"## Since {start:%-d %B %Y} ({days} days)",
            "",
            "| Model | Error since the start | Last 7 days |",
            "|---|---|---|",
            *[
                f"| {names[k]} | {r['since_start']:.2f} | {r['last_7_days']:.2f} |"
                for k, r in s.iterrows()
            ],
            "",
            "Errors in EUR/MWh (MAE), on the days where the three models have a forecast. "
            "The naive forecast copies the same day of last week on Mondays, Saturdays and "
            "Sundays, the previous day otherwise.",
            "",
            "<details>",
            "<summary>Day by day</summary>",
            "",
            *table(report["daily"].iloc[::-1], "Day"),
            "",
            "</details>",
            "",
            "<details>",
            "<summary>By hour of the day</summary>",
            "",
            *table(report["by_hour"], "Hour"),
            "",
            "</details>",
            "",
            "These tables are computed in SQL (DuckDB): "
            "[`src/be_power_forecast/sql/`](../src/be_power_forecast/sql/).",
            "",
        ]
    md += [
        f"Realised prices: {ATTRIBUTION} (www.smard.de), equal to the ENTSO-E prices. "
        f"Official prices: [Elia]({ELIA}) and the "
        "[ENTSO-E Transparency Platform](https://transparency.entsoe.eu/).",
        "",
    ]
    (PAGE / "README.md").write_text("\n".join(md))


def forecast(day: pd.Timestamp) -> None:
    """Forecast ``day`` with each model that has no forecast of it yet."""
    values = stored(LIVE / "forecasts.csv", day)
    dnn_values = stored(LIVE / "dnn_forecasts.csv", day)
    if values is not None and dnn_values is not None:
        print(f"{day.date()}: already forecast")
        return
    source = EntsoeSource()
    raw = {name: update_raw(source, name, day) for name in source.columns}
    frame = live_frame(raw, day)
    if values is None:
        values = forecast_day(frame, day)
        if values is not None:
            LIVE.mkdir(parents=True, exist_ok=True)
            append(LIVE / "forecasts.csv", day, values)
    records = []
    if values is not None and dnn_values is None:
        dnn_values, records = dnn_forecast(frame, day)
    if records:
        append(LIVE / "dnn_forecasts.csv", day, dnn_values)
        path = RESULTS_DIR / "dnn" / "live" / "summary.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        old = pd.read_csv(path) if path.exists() else pd.DataFrame()
        new = pd.DataFrame(records)
        if len(old):
            old = old[~((old["date"] == str(day.date())) & old["dnn"].isin(new["dnn"]))]
        pd.concat([old, new]).to_csv(path, index=False)
    if values is None:
        end = (day + pd.Timedelta(days=1)).tz_localize(TZ)
        unpublished = [n for n in EXOGENOUS if raw[n].index[-1] + pd.Timedelta(hours=1) < end]
        reason = (
            f"{' and '.join(unpublished)} not published yet"
            if unpublished
            else "an input of the previous days is missing"
        )
        print(f"{day.date()}: {reason}")
    else:
        print(f"{day.date()}: LEAR ensemble" + (", DNN ensemble" if dnn_values is not None else ""))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--day", help="delivery day (default: tomorrow, Brussels time)")
    parser.add_argument("--page-only", action="store_true", help="only refresh the page")
    args = parser.parse_args()
    now = pd.Timestamp.now(tz=TZ)
    tomorrow = now.tz_localize(None).normalize() + pd.Timedelta(days=1)
    day = pd.Timestamp(args.day) if args.day else tomorrow
    if not args.page_only:
        forecast(day)
    today = tomorrow - pd.Timedelta(days=1)
    try:  # SMARD unreachable: the forecasts are still stored
        update_realised(today)
        comparison = compare(today)
    except OSError as err:
        print(f"no realised prices: {err}")
        comparison = None
    report = None
    if REALISED.exists():
        files = {"lear": LIVE / "forecasts.csv", "dnn": LIVE / "dnn_forecasts.csv"}
        report = live_errors(files, REALISED, LIVE_START)
    write_page(today, comparison, report, now)


if __name__ == "__main__":
    main()
