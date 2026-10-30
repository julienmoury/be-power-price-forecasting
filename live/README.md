# Live: Belgian day-ahead prices

Since 1 October 2026, the day after the end of the backtest, the two models of the project forecast every Belgian delivery day: the LEAR ensemble and the DNN ensemble, retrained every evening exactly as in the backtest. Each forecast is then compared with the realised prices.

The forecasts use the French generation forecast, which is published after the 12:00 auction: they follow the paper, but could not have been used to bid.

Updated on 2026-10-30.

## Today, 2026-10-30

![Forecasts vs realised prices](compare.png)

Error (MAE, EUR/MWh) against the hourly mean of the realised prices:

| Naive | LEAR | DNN | Perfect hourly forecast* |
|---|---|---|---|
| 34.15 | 16.87 | 22.86 | 7.90 |

*Against the quarter-hour prices: the error a perfect hourly forecast still makes, since the models forecast hours.

## Since 1 October 2026 (29 days)

| Model | Error since the start | Last 7 days |
|---|---|---|
| DNN | 32.65 | 53.54 |
| LEAR | 32.78 | 43.23 |
| Naive | 47.62 | 71.91 |

Errors in EUR/MWh (MAE), on the days where the three models have a forecast. The naive forecast copies the same day of last week on Mondays, Saturdays and Sundays, the previous day otherwise.

<details>
<summary>Day by day</summary>

| Day | Naive | LEAR | DNN |
|---|---|---|---|
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
| 0 | 49.28 | 15.14 | 15.46 |
| 1 | 47.44 | 16.56 | 15.59 |
| 2 | 46.41 | 18.54 | 16.88 |
| 3 | 44.90 | 22.85 | 19.58 |
| 4 | 45.05 | 24.24 | 19.40 |
| 5 | 45.20 | 26.70 | 19.05 |
| 6 | 43.00 | 25.92 | 26.04 |
| 7 | 42.81 | 26.03 | 32.17 |
| 8 | 47.43 | 31.43 | 34.06 |
| 9 | 51.82 | 36.84 | 33.91 |
| 10 | 52.60 | 35.89 | 30.89 |
| 11 | 58.70 | 37.98 | 33.39 |
| 12 | 59.52 | 42.01 | 35.35 |
| 13 | 53.60 | 38.45 | 34.07 |
| 14 | 55.14 | 38.93 | 33.27 |
| 15 | 45.85 | 36.75 | 33.11 |
| 16 | 47.89 | 44.22 | 40.99 |
| 17 | 50.24 | 51.42 | 49.18 |
| 18 | 52.04 | 42.81 | 50.75 |
| 19 | 52.09 | 40.03 | 52.01 |
| 20 | 40.39 | 35.32 | 43.28 |
| 21 | 38.06 | 32.23 | 39.57 |
| 22 | 34.70 | 31.40 | 37.68 |
| 23 | 38.66 | 35.11 | 37.87 |

</details>

These tables are computed in SQL (DuckDB): [`src/be_power_forecast/sql/`](../src/be_power_forecast/sql/).

Realised prices: Bundesnetzagentur | SMARD.de, CC BY 4.0 (www.smard.de), equal to the ENTSO-E prices. Official prices: [Elia](https://www.elia.be/en/grid-data/transmission/day-ahead-reference-price) and the [ENTSO-E Transparency Platform](https://transparency.entsoe.eu/).
