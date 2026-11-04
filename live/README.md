# Live: Belgian day-ahead prices

Since 1 October 2026, the day after the end of the backtest, the two models of the project forecast every Belgian delivery day: the LEAR ensemble and the DNN ensemble, retrained every evening exactly as in the backtest. Each forecast is then compared with the realised prices.

The forecasts use the French generation forecast, which is published after the 12:00 auction: they follow the paper, but could not have been used to bid.

Updated on 2026-11-04.

## Today, 2026-11-04

![Forecasts vs realised prices](compare.png)

Error (MAE, EUR/MWh) against the hourly mean of the realised prices:

| Naive | LEAR | DNN | Perfect hourly forecast* |
|---|---|---|---|
| 10.51 | 18.22 | 8.32 | 8.83 |

*Against the quarter-hour prices: the error a perfect hourly forecast still makes, since the models forecast hours.

## Since 1 October 2026 (33 days)

| Model | Error since the start | Last 7 days |
|---|---|---|
| DNN | 32.14 | 34.78 |
| LEAR | 32.61 | 33.02 |
| Naive | 58.16 | 103.06 |

Errors in EUR/MWh (MAE), on the days where the three models have a forecast. The naive forecast copies the same day of last week on Mondays, Saturdays and Sundays, the previous day otherwise.

<details>
<summary>Day by day</summary>

| Day | Naive | LEAR | DNN |
|---|---|---|---|
| 2026-11-04 | 10.51 | 18.22 | 8.32 |
| 2026-11-03 | 13.31 | – | – |
| 2026-11-02 | 89.84 | 25.81 | 16.10 |
| 2026-11-01 | 227.41 | 45.46 | 27.00 |
| 2026-10-31 | 210.64 | 35.99 | 62.34 |
| 2026-10-30 | 34.15 | 16.87 | 22.86 |
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
| 0 | 63.21 | 14.57 | 16.36 |
| 1 | 61.34 | 16.05 | 16.63 |
| 2 | 60.89 | 18.13 | 18.10 |
| 3 | 59.51 | 22.34 | 20.33 |
| 4 | 59.44 | 23.90 | 20.01 |
| 5 | 58.75 | 25.43 | 19.70 |
| 6 | 55.40 | 26.24 | 26.55 |
| 7 | 52.64 | 27.02 | 30.88 |
| 8 | 56.13 | 31.63 | 32.81 |
| 9 | 58.75 | 36.67 | 32.76 |
| 10 | 59.90 | 35.98 | 31.37 |
| 11 | 65.09 | 37.87 | 33.83 |
| 12 | 66.52 | 41.62 | 35.57 |
| 13 | 61.78 | 37.75 | 33.14 |
| 14 | 64.10 | 38.41 | 33.99 |
| 15 | 56.73 | 38.18 | 34.24 |
| 16 | 59.41 | 44.30 | 41.83 |
| 17 | 59.86 | 49.01 | 47.55 |
| 18 | 59.42 | 40.26 | 47.25 |
| 19 | 59.69 | 38.80 | 47.92 |
| 20 | 51.10 | 36.93 | 41.17 |
| 21 | 48.96 | 33.23 | 37.52 |
| 22 | 46.51 | 32.42 | 36.05 |
| 23 | 50.74 | 35.96 | 35.76 |

</details>

These tables are computed in SQL (DuckDB): [`src/be_power_forecast/sql/`](../src/be_power_forecast/sql/).

Realised prices: Bundesnetzagentur | SMARD.de, CC BY 4.0 (www.smard.de), equal to the ENTSO-E prices. Official prices: [Elia](https://www.elia.be/en/grid-data/transmission/day-ahead-reference-price) and the [ENTSO-E Transparency Platform](https://transparency.entsoe.eu/).
