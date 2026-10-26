# Live: Belgian day-ahead prices

Since 1 October 2026, the day after the end of the backtest, the two models of the project forecast every Belgian delivery day: the LEAR ensemble and the DNN ensemble, retrained every evening exactly as in the backtest. Each forecast is then compared with the realised prices.

The forecasts use the French generation forecast, which is published after the 12:00 auction: they follow the paper, but could not have been used to bid.

Updated on 2026-10-26.

## Today, 2026-10-26

![Forecasts vs realised prices](compare.png)

Error (MAE, EUR/MWh) against the hourly mean of the realised prices:

| Naive | LEAR | DNN | Perfect hourly forecast* |
|---|---|---|---|
| 63.96 | 61.97 | 86.09 | 13.90 |

*Against the quarter-hour prices: the error a perfect hourly forecast still makes, since the models forecast hours.

## Since 1 October 2026 (25 days)

| Model | Error since the start | Last 7 days |
|---|---|---|
| DNN | 29.76 | 33.99 |
| LEAR | 31.99 | 38.90 |
| Naive | 45.57 | 55.07 |

Errors in EUR/MWh (MAE), on the days where the three models have a forecast. The naive forecast copies the same day of last week on Mondays, Saturdays and Sundays, the previous day otherwise.

<details>
<summary>Day by day</summary>

| Day | Naive | LEAR | DNN |
|---|---|---|---|
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
| 0 | 49.03 | 15.41 | 14.51 |
| 1 | 46.99 | 16.49 | 13.82 |
| 2 | 45.57 | 18.84 | 15.09 |
| 3 | 43.44 | 23.47 | 17.41 |
| 4 | 43.90 | 25.20 | 17.46 |
| 5 | 44.68 | 27.31 | 17.23 |
| 6 | 42.15 | 27.31 | 24.15 |
| 7 | 40.46 | 28.98 | 29.47 |
| 8 | 43.40 | 32.51 | 32.80 |
| 9 | 46.80 | 37.28 | 33.28 |
| 10 | 48.96 | 36.08 | 30.61 |
| 11 | 53.48 | 37.84 | 32.08 |
| 12 | 55.18 | 42.34 | 34.06 |
| 13 | 50.86 | 38.03 | 32.63 |
| 14 | 53.73 | 38.96 | 32.01 |
| 15 | 46.03 | 36.56 | 29.35 |
| 16 | 47.21 | 39.63 | 32.49 |
| 17 | 43.91 | 45.28 | 40.68 |
| 18 | 48.58 | 38.38 | 45.26 |
| 19 | 50.73 | 37.68 | 48.47 |
| 20 | 39.27 | 33.97 | 39.27 |
| 21 | 37.27 | 29.49 | 34.85 |
| 22 | 33.81 | 27.80 | 33.21 |
| 23 | 38.26 | 32.87 | 34.17 |

</details>

These tables are computed in SQL (DuckDB): [`src/be_power_forecast/sql/`](../src/be_power_forecast/sql/).

Realised prices: Bundesnetzagentur | SMARD.de, CC BY 4.0 (www.smard.de), equal to the ENTSO-E prices. Official prices: [Elia](https://www.elia.be/en/grid-data/transmission/day-ahead-reference-price) and the [ENTSO-E Transparency Platform](https://transparency.entsoe.eu/).
