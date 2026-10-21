# Live: Belgian day-ahead prices

Since 1 October 2026, the day after the end of the backtest, the two models of the project forecast every Belgian delivery day: the LEAR ensemble and the DNN ensemble, retrained every evening exactly as in the backtest. Each forecast is then compared with the realised prices.

The forecasts use the French generation forecast, which is published after the 12:00 auction: they follow the paper, but could not have been used to bid.

Updated on 2026-10-21.

## Today, 2026-10-21

![Forecasts vs realised prices](compare.png)

Error (MAE, EUR/MWh) against the hourly mean of the realised prices:

| Naive | LEAR | DNN | Perfect hourly forecast* |
|---|---|---|---|
| 19.81 | 29.61 | 11.03 | 8.26 |

*Against the quarter-hour prices: the error a perfect hourly forecast still makes, since the models forecast hours.

## Since 1 October 2026 (21 days)

| Model | Error since the start | Last 7 days |
|---|---|---|
| DNN | 26.73 | 22.00 |
| LEAR | 29.25 | 25.89 |
| Naive | 40.08 | 37.93 |

Errors in EUR/MWh (MAE), on the days where the three models have a forecast. The naive forecast copies the same day of last week on Mondays, Saturdays and Sundays, the previous day otherwise.

<details>
<summary>Day by day</summary>

| Day | Naive | LEAR | DNN |
|---|---|---|---|
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
| 2026-10-08 | 53.69 | 26.89 | 20.50 |
| 2026-10-07 | 31.47 | 27.75 | 27.52 |
| 2026-10-06 | 34.61 | 34.32 | 34.50 |
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
| 0 | 38.33 | 13.35 | 13.09 |
| 1 | 36.49 | 15.75 | 12.31 |
| 2 | 35.30 | 17.24 | 13.16 |
| 3 | 33.11 | 19.69 | 15.66 |
| 4 | 34.03 | 22.87 | 15.47 |
| 5 | 35.97 | 25.01 | 14.89 |
| 6 | 34.97 | 24.14 | 19.85 |
| 7 | 36.92 | 23.55 | 22.80 |
| 8 | 39.18 | 27.11 | 26.45 |
| 9 | 43.23 | 32.74 | 27.56 |
| 10 | 47.48 | 32.94 | 27.34 |
| 11 | 52.73 | 33.98 | 27.57 |
| 12 | 56.38 | 40.33 | 30.60 |
| 13 | 50.18 | 38.77 | 31.55 |
| 14 | 54.06 | 39.70 | 31.62 |
| 15 | 46.06 | 35.75 | 27.40 |
| 16 | 47.01 | 37.75 | 29.31 |
| 17 | 40.89 | 41.65 | 37.10 |
| 18 | 44.30 | 33.91 | 43.10 |
| 19 | 45.01 | 36.19 | 47.15 |
| 20 | 31.13 | 31.19 | 36.43 |
| 21 | 27.76 | 25.36 | 30.59 |
| 22 | 24.01 | 24.59 | 29.58 |
| 23 | 27.46 | 28.40 | 30.85 |

</details>

These tables are computed in SQL (DuckDB): [`src/be_power_forecast/sql/`](../src/be_power_forecast/sql/).

Realised prices: Bundesnetzagentur | SMARD.de, CC BY 4.0 (www.smard.de), equal to the ENTSO-E prices. Official prices: [Elia](https://www.elia.be/en/grid-data/transmission/day-ahead-reference-price) and the [ENTSO-E Transparency Platform](https://transparency.entsoe.eu/).
