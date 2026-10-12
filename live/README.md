# Live forecast of the Belgian day-ahead price

Generated automatically on 2026-10-12 17:27 (Brussels time) by `scripts/live_forecast.py`, before the 12:00 gate closure of the day-ahead auction.
The model is the 4-window LEAR ensemble of the backtests, recalibrated every morning; when an input is not published yet, the naive forecast is used and labelled.

## Delivery day 2026-10-13: `lear_ensemble`

![Forecast](forecast.png)

| Hour | 00 | 01 | 02 | 03 | 04 | 05 | 06 | 07 | 08 | 09 | 10 | 11 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| EUR/MWh | 166.5 | 156.8 | 151.5 | 150.4 | 150.0 | 159.1 | 192.4 | 223.8 | 224.4 | 188.7 | 164.4 | 142.4 |
| Hour | 12 | 13 | 14 | 15 | 16 | 17 | 18 | 19 | 20 | 21 | 22 | 23 |
| EUR/MWh | 115.6 | 105.7 | 113.2 | 126.4 | 141.1 | 173.9 | 209.8 | 231.1 | 206.8 | 175.4 | 161.1 | 144.5 |

Hourly prices; since 1 October 2025 each value is the average of four quarter-hours.

## Track record

1 delivery days scored since 2026-10-13: mean absolute error 17.18 EUR/MWh for the live forecast, 20.48 for the naive forecast.

| Delivery day | Model | MAE live | MAE naive |
|---|---|---|---|
| 2026-10-13 | lear_ensemble | 17.18 | 20.48 |

Realised prices are not shown (ENTSO-E re-use terms); they are on the [ENTSO-E Transparency Platform](https://transparency.entsoe.eu/).
