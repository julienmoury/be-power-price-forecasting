# Live: Belgian day-ahead prices

Since 1 October 2026, the day after the end of the backtest, the two models of the project forecast every Belgian delivery day: the LEAR ensemble and the DNN ensemble, retrained every evening exactly as in the backtest. Each forecast is then compared with the realised prices.

The forecasts use the French generation forecast, which is published after the 12:00 auction: they follow the paper, but could not have been used to bid.

Updated on 2026-10-23.

## Today, 2026-10-23

![Forecasts vs realised prices](compare.png)

Error (MAE, EUR/MWh) against the hourly mean of the realised prices:

| Naive | LEAR | DNN | Perfect hourly forecast* |
|---|---|---|---|
| 51.29 | 40.24 | 25.40 | 6.21 |

*Against the quarter-hour prices: the error a perfect hourly forecast still makes, since the models forecast hours.

## Since 1 October 2026 (23 days)

| Model | Error since the start | Last 7 days |
|---|---|---|
| DNN | 27.20 | 22.33 |
| LEAR | 30.06 | 31.02 |
| Naive | 41.28 | 48.50 |

Errors in EUR/MWh (MAE), on the days where the three models have a forecast. The naive forecast copies the same day of last week on Mondays, Saturdays and Sundays, the previous day otherwise.

<details>
<summary>Day by day</summary>

| Day | Naive | LEAR | DNN |
|---|---|---|---|
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
| 0 | 39.39 | 14.07 | 13.76 |
| 1 | 37.80 | 16.57 | 12.93 |
| 2 | 36.18 | 18.71 | 14.46 |
| 3 | 34.72 | 21.37 | 17.20 |
| 4 | 35.67 | 24.85 | 17.30 |
| 5 | 37.28 | 26.57 | 16.72 |
| 6 | 36.96 | 26.30 | 21.40 |
| 7 | 38.07 | 24.92 | 23.13 |
| 8 | 40.46 | 28.00 | 26.39 |
| 9 | 44.50 | 33.66 | 27.49 |
| 10 | 47.46 | 33.33 | 26.96 |
| 11 | 52.80 | 34.68 | 28.10 |
| 12 | 55.24 | 40.06 | 30.72 |
| 13 | 48.76 | 38.22 | 31.41 |
| 14 | 51.97 | 38.31 | 30.50 |
| 15 | 44.71 | 34.28 | 26.29 |
| 16 | 46.22 | 37.14 | 28.89 |
| 17 | 41.94 | 42.75 | 37.31 |
| 18 | 46.93 | 36.06 | 43.63 |
| 19 | 47.69 | 36.65 | 47.18 |
| 20 | 34.81 | 32.85 | 37.19 |
| 21 | 31.76 | 26.52 | 31.53 |
| 22 | 27.79 | 25.03 | 30.28 |
| 23 | 31.61 | 30.51 | 32.00 |

</details>

These tables are computed in SQL (DuckDB): [`src/be_power_forecast/sql/`](../src/be_power_forecast/sql/).

Realised prices: Bundesnetzagentur | SMARD.de, CC BY 4.0 (www.smard.de), equal to the ENTSO-E prices. Official prices: [Elia](https://www.elia.be/en/grid-data/transmission/day-ahead-reference-price) and the [ENTSO-E Transparency Platform](https://transparency.entsoe.eu/).
