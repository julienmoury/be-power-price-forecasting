# Live: Belgian day-ahead prices

Since 1 October 2026, the day after the end of the backtest, the two models of the project forecast every Belgian delivery day: the LEAR ensemble and the DNN ensemble, retrained every evening exactly as in the backtest. Each forecast is then compared with the realised prices.

The forecasts use the French generation forecast, which is published after the 12:00 auction: they follow the paper, but could not have been used to bid.

Updated on 2026-10-29.

## Today, 2026-10-29

![Forecasts vs realised prices](compare.png)

Error (MAE, EUR/MWh) against the hourly mean of the realised prices:

| Naive | LEAR | DNN | Perfect hourly forecast* |
|---|---|---|---|
| 45.82 | 55.78 | 72.03 | 12.68 |

*Against the quarter-hour prices: the error a perfect hourly forecast still makes, since the models forecast hours.

## Since 1 October 2026 (28 days)

| Model | Error since the start | Last 7 days |
|---|---|---|
| DNN | 33.00 | 53.96 |
| LEAR | 33.35 | 47.13 |
| Naive | 48.10 | 74.77 |

Errors in EUR/MWh (MAE), on the days where the three models have a forecast. The naive forecast copies the same day of last week on Mondays, Saturdays and Sundays, the previous day otherwise.

<details>
<summary>Day by day</summary>

| Day | Naive | LEAR | DNN |
|---|---|---|---|
| 2026-10-29 | 45.82 | 55.78 | 72.03 |
| 2026-10-28 | 90.20 | 36.29 | 53.20 |
| 2026-10-27 | 71.46 | 42.08 | 54.59 |
| 2026-10-26 | 63.96 | 61.97 | 86.09 |
| 2026-10-25 | 166.69 | – | – |
| 2026-10-24 | 125.89 | 46.39 | 32.45 |
| 2026-10-23 | 51.29 | 40.24 | 25.40 |
| 2026-10-22 | 56.38 | 36.86 | 38.93 |
| 2026-10-21 | 19.81 | 29.61 | 11.03 |
| 2026-10-20 | 13.10 | 18.30 | 10.02 |
| 2026-10-19 | 24.11 | 14.59 | 12.47 |
| 2026-10-18 | 63.55 | 57.22 | 42.36 |
| 2026-10-17 | 111.26 | 20.30 | 16.12 |
| 2026-10-16 | 23.24 | 31.44 | 47.00 |
| 2026-10-15 | 10.45 | 9.76 | 14.99 |
| 2026-10-14 | 25.88 | 15.70 | 23.25 |
| 2026-10-13 | 20.48 | 17.18 | 16.68 |
| 2026-10-12 | 27.60 | 24.92 | 33.83 |
| 2026-10-11 | 44.98 | 37.63 | 37.46 |
| 2026-10-10 | 119.78 | 50.06 | 25.05 |
| 2026-10-09 | 60.29 | 72.72 | 75.88 |
| 2026-10-08 | 53.68 | 26.89 | 20.50 |
| 2026-10-07 | 31.47 | 27.75 | 27.52 |
| 2026-10-06 | 34.61 | 34.32 | 34.51 |
| 2026-10-05 | 33.51 | 22.24 | 20.25 |
| 2026-10-04 | 52.90 | 19.91 | 10.25 |
| 2026-10-03 | 20.34 | 21.02 | 22.07 |
| 2026-10-02 | 12.24 | 21.41 | 22.01 |
| 2026-10-01 | 38.50 | 41.24 | 38.00 |

</details>

<details>
<summary>By hour of the day</summary>

| Hour | Naive | LEAR | DNN |
|---|---|---|---|
| 0 | 50.95 | 15.42 | 15.84 |
| 1 | 49.12 | 16.92 | 15.71 |
| 2 | 48.06 | 19.05 | 16.89 |
| 3 | 46.32 | 23.53 | 19.55 |
| 4 | 46.48 | 24.76 | 19.43 |
| 5 | 46.62 | 27.23 | 18.96 |
| 6 | 44.04 | 26.67 | 25.45 |
| 7 | 43.75 | 26.95 | 31.64 |
| 8 | 48.30 | 32.26 | 33.83 |
| 9 | 53.18 | 38.09 | 33.83 |
| 10 | 53.75 | 35.31 | 31.18 |
| 11 | 59.72 | 37.91 | 33.75 |
| 12 | 60.48 | 42.15 | 35.66 |
| 13 | 54.21 | 38.82 | 34.29 |
| 14 | 55.78 | 40.06 | 33.22 |
| 15 | 46.28 | 38.03 | 32.73 |
| 16 | 47.69 | 45.48 | 40.58 |
| 17 | 46.96 | 51.98 | 50.32 |
| 18 | 49.80 | 42.53 | 52.46 |
| 19 | 50.77 | 39.81 | 53.75 |
| 20 | 40.01 | 35.90 | 44.55 |
| 21 | 37.98 | 33.21 | 40.54 |
| 22 | 34.83 | 32.18 | 38.81 |
| 23 | 39.29 | 36.21 | 38.98 |

</details>

These tables are computed in SQL (DuckDB): [`src/be_power_forecast/sql/`](../src/be_power_forecast/sql/).

Realised prices: Bundesnetzagentur | SMARD.de, CC BY 4.0 (www.smard.de), equal to the ENTSO-E prices. Official prices: [Elia](https://www.elia.be/en/grid-data/transmission/day-ahead-reference-price) and the [ENTSO-E Transparency Platform](https://transparency.entsoe.eu/).
