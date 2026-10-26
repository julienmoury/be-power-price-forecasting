# Live: Belgian day-ahead prices

Since 1 October 2026, the day after the end of the backtest, the two models of the project forecast every Belgian delivery day: the LEAR ensemble and the DNN ensemble, retrained every evening exactly as in the backtest. Each forecast is then compared with the realised prices.

The forecasts use the French generation forecast, which is published after the 12:00 auction: they follow the paper, but could not have been used to bid.

Updated on 2026-10-27.

## Today, 2026-10-27

![Forecasts vs realised prices](compare.png)

Error (MAE, EUR/MWh) against the hourly mean of the realised prices:

| Naive | LEAR | DNN | Perfect hourly forecast* |
|---|---|---|---|
| 71.46 | 42.08 | 54.59 | 10.37 |

*Against the quarter-hour prices: the error a perfect hourly forecast still makes, since the models forecast hours.

## Since 1 October 2026 (26 days)

| Model | Error since the start | Last 7 days |
|---|---|---|
| DNN | 30.72 | 41.41 |
| LEAR | 32.38 | 42.86 |
| Naive | 46.57 | 64.80 |

Errors in EUR/MWh (MAE), on the days where the three models have a forecast. The naive forecast copies the same day of last week on Mondays, Saturdays and Sundays, the previous day otherwise.

<details>
<summary>Day by day</summary>

| Day | Naive | LEAR | DNN |
|---|---|---|---|
| 2026-10-27 | 71.46 | 42.08 | 54.59 |
| 2026-10-26 | 63.96 | 61.97 | 86.09 |
| 2026-10-25 | 166.68 | – | – |
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
| 0 | 50.34 | 15.14 | 14.47 |
| 1 | 48.23 | 16.46 | 13.87 |
| 2 | 46.60 | 18.40 | 14.66 |
| 3 | 44.66 | 22.76 | 17.06 |
| 4 | 44.76 | 24.28 | 17.01 |
| 5 | 44.36 | 26.99 | 17.00 |
| 6 | 41.09 | 26.95 | 23.29 |
| 7 | 41.87 | 27.92 | 29.32 |
| 8 | 46.03 | 31.99 | 31.76 |
| 9 | 50.82 | 37.48 | 33.17 |
| 10 | 51.53 | 36.48 | 31.01 |
| 11 | 57.12 | 39.24 | 33.40 |
| 12 | 58.11 | 43.42 | 34.99 |
| 13 | 51.66 | 38.34 | 33.01 |
| 14 | 53.57 | 38.55 | 31.41 |
| 15 | 44.72 | 36.11 | 30.01 |
| 16 | 46.74 | 41.07 | 35.50 |
| 17 | 42.93 | 46.11 | 43.24 |
| 18 | 47.57 | 39.44 | 47.57 |
| 19 | 49.92 | 38.22 | 50.66 |
| 20 | 39.84 | 34.97 | 42.03 |
| 21 | 38.54 | 31.53 | 38.24 |
| 22 | 35.76 | 30.14 | 36.87 |
| 23 | 40.83 | 35.03 | 37.71 |

</details>

These tables are computed in SQL (DuckDB): [`src/be_power_forecast/sql/`](../src/be_power_forecast/sql/).

Realised prices: Bundesnetzagentur | SMARD.de, CC BY 4.0 (www.smard.de), equal to the ENTSO-E prices. Official prices: [Elia](https://www.elia.be/en/grid-data/transmission/day-ahead-reference-price) and the [ENTSO-E Transparency Platform](https://transparency.entsoe.eu/).
