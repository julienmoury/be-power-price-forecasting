"""Forecast the next Belgian delivery day with the LEAR ensemble and publish it in live/.

Run every morning by .github/workflows/live.yml, before the 12:00 (Brussels) gate closure
of the day-ahead auction; needs ENTSOE_API_KEY. Steps: extend the cached ENTSO-E series,
forecast the delivery day with the LEAR ensemble, append it to
results/forecasts/live/forecasts.csv and write the page live/README.md (with
live/forecast.png). When an input is not published yet, no forecast is written and the
page says so: the naive forecast is a copy of past prices, which are never published
(ENTSO-E re-use terms).
Usage: python scripts/live_forecast.py [--day YYYY-MM-DD]
"""

from __future__ import annotations

import argparse

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from be_power_forecast.backtest import HOURS
from be_power_forecast.config import EXOGENOUS, REPO_ROOT, RESULTS_DIR, TZ
from be_power_forecast.data.sources import EntsoeSource
from be_power_forecast.live import forecast_day, live_frame, update_raw

LIVE = RESULTS_DIR / "forecasts" / "live"
PAGE = REPO_ROOT / "live"
ELIA = "https://www.elia.be/en/grid-data/transmission/day-ahead-reference-price"
BLUE, INK = "#2a78d6", "#52514e"


def write_page(day: pd.Timestamp, values: np.ndarray | None, reason: str, now) -> None:
    PAGE.mkdir(exist_ok=True)
    md = [
        "# Live forecast of the Belgian day-ahead price",
        "",
        f"Updated automatically on {now:%Y-%m-%d %H:%M} (Brussels time) by "
        "`scripts/live_forecast.py`, every morning before the 12:00 gate closure of the "
        "day-ahead auction. The model is the 4-window LEAR ensemble of the backtests, "
        "recalibrated every morning.",
        "",
        f"## Delivery day {day.date()}",
        "",
    ]
    (PAGE / "forecast.png").unlink(missing_ok=True)
    if values is None:
        md.append(f"No forecast for this day: {reason}.")
    else:
        fig, ax = plt.subplots(figsize=(7, 3), dpi=150)
        ax.step(range(25), [*values, values[-1]], where="post", color=BLUE, lw=2)
        ax.set_xticks(range(0, 25, 3))
        ax.set_xlabel("Hour (Brussels time)", color=INK)
        ax.set_ylabel("EUR/MWh", color=INK)
        ax.set_title(f"LEAR ensemble forecast for {day.date()}", color=INK, fontsize=10)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        ax.grid(axis="y", color="#e4e3df")
        fig.tight_layout()
        fig.savefig(PAGE / "forecast.png")
        plt.close(fig)
        md += [
            "![Forecast](forecast.png)",
            "",
            "| Hour | " + " | ".join(f"{h:02d}" for h in range(12)) + " |",
            "|---" * 13 + "|",
            "| EUR/MWh | " + " | ".join(f"{v:.1f}" for v in values[:12]) + " |",
            "| Hour | " + " | ".join(f"{h:02d}" for h in range(12, 24)) + " |",
            "| EUR/MWh | " + " | ".join(f"{v:.1f}" for v in values[12:]) + " |",
            "",
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
    values = forecast_day(live_frame(raw, day), day)
    end = (day + pd.Timedelta(days=1)).tz_localize(TZ)
    unpublished = [n for n in EXOGENOUS if raw[n].index[-1] + pd.Timedelta(hours=1) < end]
    reason = (
        f"{' and '.join(unpublished)} not published yet"
        if unpublished
        else "an input of the previous days is missing"
    )
    print(f"{day.date()}: " + ("LEAR ensemble" if values is not None else reason))
    if values is not None:
        LIVE.mkdir(parents=True, exist_ok=True)
        path = LIVE / "forecasts.csv"
        forecasts = (
            pd.read_csv(path, index_col=0, parse_dates=True) if path.exists() else pd.DataFrame()
        )
        row = pd.DataFrame([values], pd.DatetimeIndex([day], name="Date"), HOURS)
        forecasts = pd.concat([forecasts.drop(index=day, errors="ignore"), row]).sort_index()
        forecasts.to_csv(path, float_format="%.6f")
    write_page(day, values, reason, now)


if __name__ == "__main__":
    main()
