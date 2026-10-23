# Live: Belgian day-ahead prices

Since 1 October 2026, the day after the end of the backtest, the two models of the project forecast every Belgian delivery day: the LEAR ensemble and the DNN ensemble, retrained every evening exactly as in the backtest. Each forecast is then compared with the realised prices.

The forecasts use the French generation forecast, which is published after the 12:00 auction: they follow the paper, but could not have been used to bid.

Updated on 2026-10-24.

## Today, 2026-10-24

![Forecasts vs realised prices](compare.png)

Error (MAE, EUR/MWh) against the hourly mean of the realised prices:

| Naive | LEAR | DNN | Perfect hourly forecast* |
|---|---|---|---|
| 125.88 | 46.39 | 32.45 | 4.26 |

*Against the quarter-hour prices: the error a perfect hourly forecast still makes, since the models forecast hours.

## Since 1 October 2026 (24 days)

| Model | Error since the start | Last 7 days |
|---|---|---|
| DNN | 27.42 | 24.67 |
| LEAR | 30.74 | 34.74 |
| Naive | 44.81 | 50.59 |

Errors in EUR/MWh (MAE), on the days where the three models have a forecast. The naive forecast copies the same day of last week on Mondays, Saturdays and Sundays, the previous day otherwise.

<details>
<summary>Day by day</summary>

| Day | Naive | LEAR | DNN |
|---|---|---|---|
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
| 0 | 44.86 | 13.90 | 14.49 |
| 1 | 42.70 | 16.02 | 13.40 |
| 2 | 40.74 | 19.21 | 14.98 |
| 3 | 38.61 | 24.03 | 17.43 |
| 4 | 39.37 | 25.98 | 17.50 |
| 5 | 40.90 | 27.77 | 17.01 |
| 6 | 40.67 | 26.94 | 21.91 |
| 7 | 41.84 | 24.66 | 23.49 |
| 8 | 44.45 | 27.72 | 26.20 |
| 9 | 47.52 | 32.63 | 26.66 |
| 10 | 50.47 | 32.72 | 26.19 |
| 11 | 55.04 | 34.13 | 27.72 |
| 12 | 56.97 | 39.57 | 30.38 |
| 13 | 50.42 | 37.97 | 31.14 |
| 14 | 53.67 | 38.23 | 30.44 |
| 15 | 47.03 | 34.48 | 26.78 |
| 16 | 48.69 | 37.35 | 29.52 |
| 17 | 45.35 | 43.02 | 37.35 |
| 18 | 49.87 | 36.49 | 42.43 |
| 19 | 51.32 | 37.78 | 46.12 |
| 20 | 38.74 | 34.57 | 37.50 |
| 21 | 37.11 | 29.97 | 33.24 |
| 22 | 32.60 | 28.64 | 32.06 |
| 23 | 36.37 | 33.95 | 34.05 |

</details>

These tables are computed in SQL (DuckDB): [`src/be_power_forecast/sql/`](../src/be_power_forecast/sql/).

Realised prices: Bundesnetzagentur | SMARD.de, CC BY 4.0 (www.smard.de), equal to the ENTSO-E prices. Official prices: [Elia](https://www.elia.be/en/grid-data/transmission/day-ahead-reference-price) and the [ENTSO-E Transparency Platform](https://transparency.entsoe.eu/).
