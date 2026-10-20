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
written. A day already forecast is not forecast again (the workflow runs twice, the second
time as a fallback). The page live/README.md only shows today: today's forecasts (made the
evening before) against today's realised prices, taken from SMARD.de (CC BY 4.0; the
ENTSO-E prices are not on its free re-use list): quarter-hours and their hourly mean, the
naive forecast, LEAR and DNN on one chart (live/compare.png), with the MAE of each.
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


def write_page(today: pd.Timestamp, c: dict | None, now) -> None:
    """The live page: today's forecasts (made the evening before) vs today's prices."""
    PAGE.mkdir(exist_ok=True)
    for old in ("compare.png", "forecast.png"):
        (PAGE / old).unlink(missing_ok=True)
    md = [
        "# Belgian day-ahead price: today's forecasts vs realised prices",
        "",
        f"Updated automatically on {now:%Y-%m-%d %H:%M} (Brussels time) by "
        "`scripts/live_forecast.py`, every evening. The two models of the backtests, the "
        "4-window LEAR ensemble and the ensemble of the four DNNs of Lago et al. (2021), are "
        "recalibrated every evening and forecast the next day, once the French day-ahead "
        "generation forecast, one of their inputs, is published on ENTSO-E (by 18:00, after "
        "the 12:00 auction: these forecasts use the information of the paper but could not "
        "be used to bid). The next evening, they are compared here with the realised prices.",
        "",
        f"## Today, {today.date()}",
        "",
    ]
    if c is None:
        md += ["Not available: no forecast of today, or its prices are not complete.", ""]
    else:
        compare_chart(today, c)
        m = c["mae"]
        fmt = lambda v: "–" if v is None else f"{v:.2f}"  # noqa: E731
        md += [
            "![Forecasts vs realised prices](compare.png)",
            "",
            "Mean absolute error (EUR/MWh) against the hourly mean of the realised prices:",
            "",
            "| Naive | LEAR | DNN | Perfect hourly forecast* |",
            "|---|---|---|---|",
            f"| {fmt(m['naive'])} | {fmt(m['lear'])} | {fmt(m['dnn'])} | {fmt(m['perfect'])} |",
            "",
            "*Against the quarter-hour prices: the error a perfect hourly forecast still makes, "
            "since the models forecast hours. The naive forecast copies the same day of last "
            "week on Mondays, Saturdays and Sundays, the previous day otherwise.",
            "",
            f"Realised prices: {ATTRIBUTION} (www.smard.de), equal to the ENTSO-E prices.",
            "",
        ]
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
        comparison = compare(today)
    except OSError as err:  # SMARD unreachable: tomorrow's forecasts are still stored
        print(f"no comparison: {err}")
        comparison = None
    write_page(today, comparison, now)


if __name__ == "__main__":
    main()
