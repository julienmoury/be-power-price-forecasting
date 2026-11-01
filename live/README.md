# Live: Belgian day-ahead prices

Since 1 October 2026, the day after the end of the backtest, the two models of the project forecast every Belgian delivery day: the LEAR ensemble and the DNN ensemble, retrained every evening exactly as in the backtest. Each forecast is then compared with the realised prices.

The forecasts use the French generation forecast, which is published after the 12:00 auction: they follow the paper, but could not have been used to bid.

Updated on 2026-11-02.

## Today, 2026-11-02

![Forecasts vs realised prices](compare.png)

Error (MAE, EUR/MWh) against the hourly mean of the realised prices:

| Naive | LEAR | DNN | Perfect hourly forecast* |
|---|---|---|---|
| 89.83 | 25.81 | 16.09 | 7.75 |

*Against the quarter-hour prices: the error a perfect hourly forecast still makes, since the models forecast hours.

## Since 1 October 2026 (32 days)

| Model | Error since the start | Last 7 days |
|---|---|---|
| DNN | 32.88 | 44.02 |
| LEAR | 33.06 | 36.90 |
| Naive | 59.65 | 109.93 |

Errors in EUR/MWh (MAE), on the days where the three models have a forecast. The naive forecast copies the same day of last week on Mondays, Saturdays and Sundays, the previous day otherwise.

<details>
<summary>Day by day</summary>

| Day | Naive | LEAR | DNN |
|---|---|---|---|
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
| 0 | 64.97 | 15.01 | 16.61 |
| 1 | 63.14 | 16.16 | 17.03 |
| 2 | 62.61 | 18.22 | 18.55 |
| 3 | 60.75 | 22.81 | 20.93 |
| 4 | 60.69 | 24.31 | 20.61 |
| 5 | 60.10 | 26.18 | 19.90 |
| 6 | 56.00 | 26.40 | 26.46 |
| 7 | 53.30 | 27.62 | 31.51 |
| 8 | 57.67 | 32.58 | 33.68 |
| 9 | 60.38 | 37.77 | 33.58 |
| 10 | 61.53 | 37.08 | 31.58 |
| 11 | 66.61 | 38.91 | 34.35 |
| 12 | 68.24 | 42.38 | 36.45 |
| 13 | 63.41 | 38.17 | 34.15 |
| 14 | 65.65 | 38.99 | 34.82 |
| 15 | 58.21 | 38.26 | 35.20 |
| 16 | 61.22 | 43.75 | 42.27 |
| 17 | 61.23 | 49.29 | 48.67 |
| 18 | 61.19 | 40.79 | 48.58 |
| 19 | 61.54 | 39.25 | 49.34 |
| 20 | 52.65 | 37.23 | 42.36 |
| 21 | 50.44 | 33.49 | 38.57 |
| 22 | 47.89 | 32.70 | 37.18 |
| 23 | 52.18 | 36.13 | 36.81 |

</details>

These tables are computed in SQL (DuckDB): [`src/be_power_forecast/sql/`](../src/be_power_forecast/sql/).

Realised prices: Bundesnetzagentur | SMARD.de, CC BY 4.0 (www.smard.de), equal to the ENTSO-E prices. Official prices: [Elia](https://www.elia.be/en/grid-data/transmission/day-ahead-reference-price) and the [ENTSO-E Transparency Platform](https://transparency.entsoe.eu/).
