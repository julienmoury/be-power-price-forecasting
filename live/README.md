# Belgian day-ahead price: today's forecasts vs realised prices

Updated automatically on 2026-10-20 22:48 (Brussels time) by `scripts/live_forecast.py`, every evening. The two models of the backtests, the 4-window LEAR ensemble and the ensemble of the four DNNs of Lago et al. (2021), are recalibrated every evening and forecast the next day, once the French day-ahead generation forecast, one of their inputs, is published on ENTSO-E (by 18:00, after the 12:00 auction: these forecasts use the information of the paper but could not be used to bid). The next evening, they are compared here with the realised prices.

## Today, 2026-10-20

![Forecasts vs realised prices](compare.png)

Mean absolute error (EUR/MWh) against the hourly mean of the realised prices:

| Naive | LEAR | DNN | Perfect hourly forecast* |
|---|---|---|---|
| 13.10 | 18.30 | 10.02 | 6.58 |

*Against the quarter-hour prices: the error a perfect hourly forecast still makes, since the models forecast hours. The naive forecast copies the same day of last week on Mondays, Saturdays and Sundays, the previous day otherwise.

Realised prices: Bundesnetzagentur | SMARD.de, CC BY 4.0 (www.smard.de), equal to the ENTSO-E prices.

Official prices: [Elia](https://www.elia.be/en/grid-data/transmission/day-ahead-reference-price) and the [ENTSO-E Transparency Platform](https://transparency.entsoe.eu/).
