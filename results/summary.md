## Reproduction of Lago et al. (2021), BE test period
|  | MAE (ours) | MAE (published) | sMAPE % (ours) | sMAPE % (published) | mean |ours - published| |
|---|---|---|---|---|---|
| LEAR 56 | 7.226 | 6.924 | 16.892 | 16.197 | 1.903 |
| LEAR 84 | 7.197 | 6.798 | 17.008 | 15.954 | 1.972 |
| LEAR 1092 | 6.606 | 6.594 | 16.919 | 16.867 | 0.141 |
| LEAR 1456 | 6.645 | 6.634 | 17.361 | 17.293 | 0.197 |
| LEAR Ensemble | 6.278 | 6.140 | 14.966 | 14.546 | 0.881 |
| LEAR 56, exog. lags D-1/D-2 (pre-2024 library) | 7.245 | 6.924 | 16.955 | 16.197 | 2.291 |
| LEAR 84, exog. lags D-1/D-2 (pre-2024 library) | 7.285 | 6.798 | 17.255 | 15.954 | 2.469 |

## Accuracy on the test period (728 days)
|  | MAE | RMSE | sMAPE_pct | rMAE |
|---|---|---|---|---|
| Naive | 8.203 | 18.689 | 19.646 | 0.997 |
| LEAR 56 | 7.226 | 16.826 | 16.892 | 0.878 |
| LEAR 84 | 7.197 | 16.705 | 17.008 | 0.874 |
| LEAR 1092 | 6.606 | 16.466 | 16.919 | 0.803 |
| LEAR 1456 | 6.645 | 16.422 | 17.361 | 0.807 |
| LEAR Ens. | 6.278 | 16.044 | 14.966 | 0.763 |

## Headline
```
{
 "naive_MAE": 8.20295673076923,
 "ensemble_MAE": 6.278287053156479,
 "ensemble_vs_naive_EUR_MWh": 1.9246696776127514,
 "ensemble_vs_naive_pct": 23.463121174263048,
 "best_single_window": 1092,
 "best_single_MAE": 6.606400448031136,
 "ensemble_vs_best_single_EUR_MWh": 0.3281133948746566,
 "ensemble_vs_best_single_pct": 4.9665986410563745,
 "dm_p_ensemble_better_than_naive": 1.3133938381315602e-13,
 "dm_p_ensemble_better_than_best_single": 1.2898622802071102e-06,
 "ensemble_vs_naive_EUR_per_MW_year": 16813.914303624995
}
```

## Multivariate DM p-values (H1: column more accurate than row)
|  | Naive | LEAR 56 | LEAR 84 | LEAR 1092 | LEAR 1456 | LEAR Ens. |
|---|---|---|---|---|---|---|
| Naive | nan | 0.0001 | 0.0001 | 0.0000 | 0.0000 | 0.0000 |
| LEAR 56 | 0.9999 | nan | 0.3560 | 0.0000 | 0.0000 | 0.0000 |
| LEAR 84 | 0.9999 | 0.6440 | nan | 0.0000 | 0.0000 | 0.0000 |
| LEAR 1092 | 1.0000 | 1.0000 | 1.0000 | nan | 0.9084 | 0.0000 |
| LEAR 1456 | 1.0000 | 1.0000 | 1.0000 | 0.0916 | nan | 0.0000 |
| LEAR Ens. | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | nan |

## Published results quoted for reference (MAE, not recomputed models)
```
{
 "source": "Lago et al. (2021), forecasts published in jeslago/epftoolbox",
 "MAE": {
  "LEAR Ensemble": 6.140060611263736,
  "DNN Ensemble": 5.869865859211077
 }
}
```

## Attribution of the MAE gap, LEAR ens. vs naive, by season
|  | hours | MAE_A | MAE_B | weight | gap | contribution | share |
|---|---|---|---|---|---|---|---|
| DJF | 4272.000 | 5.041 | 6.375 | 0.245 | -1.334 | -0.326 | 0.170 |
| JJA | 4416.000 | 5.300 | 7.213 | 0.253 | -1.913 | -0.483 | 0.251 |
| MAM | 4416.000 | 5.017 | 6.985 | 0.253 | -1.969 | -0.498 | 0.259 |
| SON | 4368.000 | 9.753 | 12.223 | 0.250 | -2.469 | -0.617 | 0.321 |
| total | 17472.000 | 6.278 | 8.203 | 1.000 | -1.925 | -1.925 | 1.000 |

## Attribution of the MAE gap, LEAR ens. vs naive, by regime
|  | hours | MAE_A | MAE_B | weight | gap | contribution | share |
|---|---|---|---|---|---|---|---|
| negative | 2.000 | 11.724 | 22.985 | 0.000 | -11.261 | -0.001 | 0.001 |
| normal | 16601.000 | 4.926 | 6.839 | 0.950 | -1.913 | -1.817 | 0.944 |
| spike | 869.000 | 32.098 | 34.227 | 0.050 | -2.130 | -0.106 | 0.055 |
| total | 17472.000 | 6.278 | 8.203 | 1.000 | -1.925 | -1.925 | 1.000 |

Hour contributions, LEAR ens. vs naive: 0: -0.092, 1: -0.075, 2: -0.081, 3: -0.081, 4: -0.075, 5: -0.067, 6: -0.071, 7: -0.106, 8: -0.089, 9: -0.095, 10: -0.095, 11: -0.096, 12: -0.083, 13: -0.070, 14: -0.084, 15: -0.073, 16: -0.082, 17: -0.077, 18: -0.104, 19: -0.095, 20: -0.071, 21: -0.047, 22: -0.054, 23: -0.063, total: -1.925

## Calibration window
|  | MAE | rMAE |
|---|---|---|
| 28 | 7.419 | 0.901 |
| 56 | 7.226 | 0.878 |
| 84 | 7.197 | 0.874 |
| 182 | 7.100 | 0.863 |
| 364 | 6.788 | 0.825 |
| 728 | 6.527 | 0.793 |
| 1092 | 6.606 | 0.803 |
| 1456 | 6.645 | 0.807 |

## Inputs removed (ensemble of the 4 windows)
|  | MAE ensemble | MAE 56 | MAE 84 | MAE 1092 | MAE 1456 | delta vs baseline | DM p (baseline better) |
|---|---|---|---|---|---|---|---|
| all inputs (baseline) | 6.278 | 7.226 | 7.197 | 6.606 | 6.645 | nan | nan |
| without FR load forecast | 6.400 | 7.343 | 7.407 | 6.664 | 6.727 | 0.121 | 0.000 |
| without FR generation forecast | 6.345 | 7.436 | 7.356 | 6.520 | 6.588 | 0.067 | 0.004 |
| without any exogenous input | 6.793 | 8.187 | 8.003 | 6.679 | 6.722 | 0.515 | 0.000 |

## Sub-periods
|  | days | mean price | MAE naive | MAE LEAR ens. | gain % | MAE 56 | MAE 84 | MAE 1092 | MAE 1456 | DM p (ens. better than naive) |
|---|---|---|---|---|---|---|---|---|---|---|
| 2015 | 362.000 | 44.704 | 9.441 | 7.423 | 21.380 | 8.750 | 8.730 | 7.303 | 7.241 | 0.000 |
| 2016 | 366.000 | 36.613 | 6.978 | 5.146 | 26.250 | 5.720 | 5.680 | 5.918 | 6.056 | 0.000 |
| Q4 2016 (FR nuclear inspections) | 92.000 | 58.097 | 13.482 | 10.008 | 25.767 | 11.490 | 11.338 | 10.427 | 10.345 | 0.001 |
| Jan-Sep 2016 | 274.000 | 29.399 | 4.794 | 3.514 | 26.707 | 3.782 | 3.780 | 4.403 | 4.616 | 0.000 |
| spike days (daily max > 95) | 37.000 | 84.743 | 31.049 | 27.297 | 12.083 | 28.659 | 27.210 | 29.134 | 28.681 | 0.177 |
| other days | 691.000 | 38.274 | 6.980 | 5.153 | 26.174 | 6.079 | 6.125 | 5.400 | 5.465 | 0.000 |
| weekday peak 08-20h | 520.000 | 50.369 | 10.413 | 8.116 | 22.053 | 9.165 | 9.077 | 8.473 | 8.532 | 0.000 |
| weekday off-peak | 520.000 | 37.626 | 6.635 | 5.068 | 23.616 | 5.860 | 5.779 | 5.290 | 5.286 | 0.000 |

