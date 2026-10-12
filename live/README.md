# Live forecast of the Belgian day-ahead price

Updated automatically on 2026-10-12 18:02 (Brussels time) by `scripts/live_forecast.py`, every morning before the 12:00 gate closure of the day-ahead auction. The model is the 4-window LEAR ensemble of the backtests, recalibrated every morning; when an input is not published yet, the naive forecast is used and labelled.

## Delivery day 2026-10-13: `lear_ensemble` (backtest, made 2026-10-12 18:02)

![Forecast](forecast.png)

| Hour | 00 | 01 | 02 | 03 | 04 | 05 | 06 | 07 | 08 | 09 | 10 | 11 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| EUR/MWh | 166.5 | 156.8 | 151.5 | 150.4 | 150.0 | 159.1 | 192.4 | 223.8 | 224.4 | 188.7 | 164.4 | 142.4 |
| Hour | 12 | 13 | 14 | 15 | 16 | 17 | 18 | 19 | 20 | 21 | 22 | 23 |
| EUR/MWh | 115.6 | 105.7 | 113.2 | 126.4 | 141.1 | 173.9 | 209.8 | 231.1 | 206.8 | 175.4 | 161.1 | 144.5 |

Hourly prices; since 1 October 2025 each value is the average of four quarter-hours.

## Track record

No live forecast has been scored yet (prices are published the day before delivery, so a forecast is scored one day after its delivery day).

Origin: `live` = made the morning before the auction; `backtest` = computed afterwards with the days before it only (days before the live service started).

| Delivery day | Origin | Model | MAE forecast | MAE naive |
|---|---|---|---|---|
| 2026-10-13 | backtest | lear_ensemble | 17.18 | 20.48 |
| 2026-10-12 | backtest | lear_ensemble | 24.92 | 27.60 |
| 2026-10-11 | backtest | lear_ensemble | 37.63 | 44.98 |
| 2026-10-10 | backtest | lear_ensemble | 50.06 | 119.78 |
| 2026-10-09 | backtest | lear_ensemble | 72.73 | 60.29 |
| 2026-10-08 | backtest | lear_ensemble | 26.89 | 53.69 |
| 2026-10-07 | backtest | lear_ensemble | 27.75 | 31.46 |
| 2026-10-06 | backtest | lear_ensemble | 34.33 | 34.61 |
| 2026-10-05 | backtest | lear_ensemble | 22.24 | 33.51 |
| 2026-10-04 | backtest | lear_ensemble | 19.91 | 52.90 |
| 2026-10-03 | backtest | lear_ensemble | 21.02 | 20.34 |
| 2026-10-02 | backtest | lear_ensemble | 21.41 | 12.24 |
| 2026-10-01 | backtest | lear_ensemble | 41.24 | 38.50 |

Realised prices are not shown (ENTSO-E re-use terms); they are on the [ENTSO-E Transparency Platform](https://transparency.entsoe.eu/).
