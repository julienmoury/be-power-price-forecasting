# Live: Belgian day-ahead prices

Since 1 October 2026, the day after the end of the backtest, the two models of the project forecast every Belgian delivery day: the LEAR ensemble and the DNN ensemble, retrained every evening exactly as in the backtest. Each forecast is then compared with the realised prices.

The forecasts use the French generation forecast, which is published after the 12:00 auction: they follow the paper, but could not have been used to bid.

Updated on 2026-10-28.

## Today, 2026-10-28

![Forecasts vs realised prices](compare.png)

Error (MAE, EUR/MWh) against the hourly mean of the realised prices:

| Naive | LEAR | DNN | Perfect hourly forecast* |
|---|---|---|---|
| 90.20 | 36.29 | 53.20 | 9.92 |

*Against the quarter-hour prices: the error a perfect hourly forecast still makes, since the models forecast hours.

## Since 1 October 2026 (27 days)

| Model | Error since the start | Last 7 days |
|---|---|---|
| DNN | 31.55 | 48.44 |
| LEAR | 32.52 | 43.97 |
| Naive | 48.18 | 76.53 |

Errors in EUR/MWh (MAE), on the days where the three models have a forecast. The naive forecast copies the same day of last week on Mondays, Saturdays and Sundays, the previous day otherwise.

<details>
<summary>Day by day</summary>

| Day | Naive | LEAR | DNN |
|---|---|---|---|
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
| 0 | 52.26 | 15.71 | 15.56 |
| 1 | 50.13 | 17.08 | 15.08 |
| 2 | 49.30 | 19.39 | 16.21 |
| 3 | 47.26 | 23.64 | 18.60 |
| 4 | 47.30 | 24.92 | 18.54 |
| 5 | 47.21 | 27.08 | 17.97 |
| 6 | 43.91 | 26.19 | 24.07 |
| 7 | 44.38 | 27.89 | 30.46 |
| 8 | 48.55 | 32.43 | 32.34 |
| 9 | 53.51 | 37.45 | 33.11 |
| 10 | 53.68 | 35.51 | 30.47 |
| 11 | 59.57 | 37.86 | 32.63 |
| 12 | 60.41 | 42.38 | 34.36 |
| 13 | 53.98 | 37.88 | 32.63 |
| 14 | 55.24 | 38.49 | 31.15 |
| 15 | 45.42 | 36.47 | 30.51 |
| 16 | 46.99 | 42.25 | 37.31 |
| 17 | 43.92 | 46.66 | 44.73 |
| 18 | 48.47 | 39.32 | 48.89 |
| 19 | 50.41 | 37.83 | 51.87 |
| 20 | 40.26 | 35.04 | 43.56 |
| 21 | 38.68 | 32.42 | 40.00 |
| 22 | 35.54 | 31.07 | 38.40 |
| 23 | 40.03 | 35.56 | 38.80 |

</details>

These tables are computed in SQL (DuckDB): [`src/be_power_forecast/sql/`](../src/be_power_forecast/sql/).

Realised prices: Bundesnetzagentur | SMARD.de, CC BY 4.0 (www.smard.de), equal to the ENTSO-E prices. Official prices: [Elia](https://www.elia.be/en/grid-data/transmission/day-ahead-reference-price) and the [ENTSO-E Transparency Platform](https://transparency.entsoe.eu/).
