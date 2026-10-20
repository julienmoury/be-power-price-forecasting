# Live forecast of the Belgian day-ahead price

Updated automatically on 2026-10-20 10:42 (Brussels time) by `scripts/live_forecast.py`, every evening once the French day-ahead generation forecast of the next day is published on ENTSO-E (by 18:00, after the 12:00 auction: these forecasts use the information of the paper but could not be used to bid). Two models of the backtests, recalibrated every day and shown side by side (not averaged): the 4-window LEAR ensemble and the ensemble of the four DNNs of Lago et al. (2021).

## Delivery day 2026-10-21

No forecast for this day: Generation forecast FR not published yet.

## Today, 2026-10-20: forecasts vs realised prices

![Forecasts vs realised prices](compare.png)

Forecasts made the evening before (after the auction, with the information of the paper). MAE in EUR/MWh against the hourly mean of the realised prices.

| | Naive | LEAR | DNN | Perfect hourly forecast |
|---|---|---|---|---|
| 2026-10-20 | 13.10 | 18.30 | 10.02 | 6.58* |
| Last 30 days, mean of 1 days with the three forecasts | 13.10 | 18.30 | 10.02 | 6.58* |

DNN more accurate than LEAR on 1 of these 1 days. *Against the quarter-hour prices: the error a perfect hourly forecast still makes, since the models forecast hours.

Realised prices: Bundesnetzagentur | SMARD.de, CC BY 4.0 (www.smard.de), equal to the ENTSO-E prices.

Official prices: [Elia](https://www.elia.be/en/grid-data/transmission/day-ahead-reference-price) and the [ENTSO-E Transparency Platform](https://transparency.entsoe.eu/).
