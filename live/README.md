# Live forecast of the Belgian day-ahead price

Updated automatically on 2026-10-13 17:55 (Brussels time) by `scripts/live_forecast.py`, every morning before the 12:00 gate closure of the day-ahead auction. The model is the 4-window LEAR ensemble of the backtests, recalibrated every morning.

## Delivery day 2026-10-14

![Forecast](forecast.png)

| Hour | 00 | 01 | 02 | 03 | 04 | 05 | 06 | 07 | 08 | 09 | 10 | 11 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| EUR/MWh | 191.5 | 179.9 | 173.3 | 170.0 | 177.0 | 181.2 | 226.1 | 253.9 | 254.3 | 218.4 | 200.3 | 157.3 |
| Hour | 12 | 13 | 14 | 15 | 16 | 17 | 18 | 19 | 20 | 21 | 22 | 23 |
| EUR/MWh | 141.2 | 127.1 | 123.6 | 146.4 | 173.1 | 211.3 | 259.3 | 281.2 | 253.5 | 216.6 | 206.5 | 185.4 |

Hourly prices; since 1 October 2025 each value is the average of four quarter-hours.

The official prices of this day are published after the 12:00 auction, around 13:00, by [Elia](https://www.elia.be/en/grid-data/transmission/day-ahead-reference-price) and the [ENTSO-E Transparency Platform](https://transparency.entsoe.eu/); they are not reproduced here (ENTSO-E re-use terms).
