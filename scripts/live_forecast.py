"""Forecast the next Belgian delivery day with the LEAR ensemble and publish it in live/.

Run every morning by .github/workflows/live.yml, before the 12:00 (Brussels) gate closure
of the day-ahead auction; needs ENTSOE_API_KEY. Steps: extend the cached ENTSO-E series,
forecast the delivery day (naive forecast if an input is not published yet), score the past
live forecasts whose prices are now known, and write
results/forecasts/live/{forecasts,scores}.csv and the page live/README.md (with
live/forecast.png). Realised prices are never written (ENTSO-E re-use terms).
Usage: python scripts/live_forecast.py [--day YYYY-MM-DD]
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from be_power_forecast.backtest import HOURS, daily_prices
from be_power_forecast.config import EXOGENOUS, RESULTS_DIR, TZ
from be_power_forecast.data.calendar import standard_frame
from be_power_forecast.data.sources import EntsoeSource
from be_power_forecast.live import forecast_day, live_frame, score, update_raw

ROOT = Path(__file__).resolve().parents[1]
LIVE = RESULTS_DIR / "forecasts" / "live"
PAGE = ROOT / "live"
BLUE, GREY, INK = "#2a78d6", "#8a8984", "#52514e"


def write_page(forecasts: pd.DataFrame, scores: pd.DataFrame, now: pd.Timestamp) -> None:
    PAGE.mkdir(exist_ok=True)
    day = forecasts.index[-1]
    last = forecasts.loc[day]
    values = last[HOURS].to_numpy(dtype=float)
    fig, ax = plt.subplots(figsize=(7, 3), dpi=150)
    ax.step(range(25), [*values, values[-1]], where="post", color=BLUE, lw=2)
    ax.set_xticks(range(0, 25, 3))
    ax.set_xlabel("Hour (Brussels time)", color=INK)
    ax.set_ylabel("EUR/MWh", color=INK)
    ax.set_title(f"Forecast for {day.date()} ({last['model']})", color=INK, fontsize=10)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.grid(axis="y", color="#e4e3df")
    fig.tight_layout()
    fig.savefig(PAGE / "forecast.png")
    plt.close(fig)

    md = [
        "# Live forecast of the Belgian day-ahead price",
        "",
        f"Generated automatically on {now:%Y-%m-%d %H:%M} (Brussels time) by "
        "`scripts/live_forecast.py`, before the 12:00 gate closure of the day-ahead auction.",
        "The model is the 4-window LEAR ensemble of the backtests, recalibrated every morning; "
        "when an input is not published yet, the naive forecast is used and labelled.",
        "",
        f"## Delivery day {day.date()}: `{last['model']}`",
        "",
        "![Forecast](forecast.png)",
        "",
        "| Hour | " + " | ".join(f"{h:02d}" for h in range(12)) + " |",
        "|---" * 13 + "|",
        "| EUR/MWh | " + " | ".join(f"{v:.1f}" for v in values[:12]) + " |",
        "| Hour | " + " | ".join(f"{h:02d}" for h in range(12, 24)) + " |",
        "| EUR/MWh | " + " | ".join(f"{v:.1f}" for v in values[12:]) + " |",
        "",
        "Hourly prices; since 1 October 2025 each value is the average of four quarter-hours.",
        "",
        "## Track record",
        "",
    ]
    if scores.empty:
        md.append("No live forecast has been scored yet (prices are published the day before "
                  "delivery, so a forecast is scored one day after its delivery day).")  # fmt: skip
    else:
        md += [
            f"{len(scores)} delivery days scored since {scores.index[0].date()}: mean absolute "
            f"error {scores['MAE'].mean():.2f} EUR/MWh for the live forecast, "
            f"{scores['MAE naive'].mean():.2f} for the naive forecast.",
            "",
            "| Delivery day | Model | MAE live | MAE naive |",
            "|---|---|---|---|",
        ]
        for d, r in scores.iloc[::-1].head(30).iterrows():
            md.append(f"| {d.date()} | {r['model']} | {r['MAE']:.2f} | {r['MAE naive']:.2f} |")
    md += [
        "",
        "Realised prices are not shown (ENTSO-E re-use terms); they are on the "
        "[ENTSO-E Transparency Platform](https://transparency.entsoe.eu/).",
        "",
    ]
    (PAGE / "README.md").write_text("\n".join(md))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--day", help="delivery day (default: tomorrow, Brussels time)")
    args = parser.parse_args()
    now = pd.Timestamp.now(tz=TZ)
    day = (
        pd.Timestamp(args.day)
        if args.day
        else now.tz_localize(None).normalize() + pd.Timedelta(days=1)
    )

    source = EntsoeSource()
    raw = {name: update_raw(source, name, day) for name in source.columns}
    result = forecast_day(live_frame(raw, day), day)
    if result is None:
        raise SystemExit(f"no forecast for {day.date()}: inputs and naive reference missing")
    model, values = result

    LIVE.mkdir(parents=True, exist_ok=True)
    path = LIVE / "forecasts.csv"
    forecasts = (
        pd.read_csv(path, index_col=0, parse_dates=True) if path.exists() else pd.DataFrame()
    )
    row = pd.DataFrame(
        [
            {
                "model": model,
                "generated_at": now.strftime("%Y-%m-%d %H:%M"),
                **dict(zip(HOURS, values, strict=True)),
            }
        ],  # fmt: skip
        index=pd.DatetimeIndex([day], name="Date"),
    )
    forecasts = pd.concat([forecasts.drop(index=day, errors="ignore"), row]).sort_index()
    forecasts.to_csv(path, float_format="%.6f")
    prices = daily_prices(standard_frame({"Price": raw["Price"]})[0])
    scores = score(forecasts, prices)
    scores.to_csv(LIVE / "scores.csv", float_format="%.6f")
    write_page(forecasts, scores, now)
    published = [name for name in EXOGENOUS if raw[name].index[-1] >= day.tz_localize(TZ)]
    print(f"{day.date()}: {model}; French forecasts published for the day: {published}")


if __name__ == "__main__":
    main()
