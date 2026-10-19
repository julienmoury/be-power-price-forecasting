## Reproduction of Lago et al. (2021), BE test period
|  | MAE (ours) | MAE (published) | sMAPE % (ours) | sMAPE % (published) | mean abs gap to published |
|---|---|---|---|---|---|
| LEAR 56 | 7.226 | 6.924 | 16.892 | 16.197 | 1.903 |
| LEAR 84 | 7.197 | 6.798 | 17.008 | 15.954 | 1.972 |
| LEAR 1092 | 6.606 | 6.594 | 16.919 | 16.867 | 0.141 |
| LEAR 1456 | 6.645 | 6.634 | 17.361 | 17.293 | 0.197 |
| LEAR Ensemble | 6.278 | 6.140 | 14.966 | 14.546 | 0.881 |
| LEAR 56, pre-2024 exogenous lags (d-1, d-2) | 7.245 | 6.924 | 16.955 | 16.197 | 2.291 |
| LEAR 84, pre-2024 exogenous lags (d-1, d-2) | 7.285 | 6.798 | 17.255 | 15.954 | 2.469 |

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
 "gw_p_ensemble_better_than_naive": 3.0531133177191805e-14,
 "gw_p_ensemble_better_than_best_single": 6.686923782472931e-07,
 "dm_p_ensemble_better_than_naive": 1.3133938381315602e-13,
 "dm_p_ensemble_better_than_best_single": 1.2898622802071102e-06,
 "ensemble_vs_naive_EUR_per_MW_year": 16813.914303624995
}
```

## Multivariate GW p-values (H1: column more accurate than row)
|  | Naive | LEAR 56 | LEAR 84 | LEAR 1092 | LEAR 1456 | LEAR Ens. |
|---|---|---|---|---|---|---|
| Naive | nan | 0.0000 | 0.0001 | 0.0000 | 0.0000 | 0.0000 |
| LEAR 56 | 1.0000 | nan | 0.3027 | 0.0000 | 0.0000 | 0.0000 |
| LEAR 84 | 1.0000 | 1.0000 | nan | 0.0000 | 0.0000 | 0.0000 |
| LEAR 1092 | 1.0000 | 1.0000 | 1.0000 | nan | 1.0000 | 0.0000 |
| LEAR 1456 | 1.0000 | 1.0000 | 1.0000 | 0.0250 | nan | 0.0000 |
| LEAR Ens. | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | nan |

## Multivariate DM p-values (H1: column more accurate than row)
|  | Naive | LEAR 56 | LEAR 84 | LEAR 1092 | LEAR 1456 | LEAR Ens. |
|---|---|---|---|---|---|---|
| Naive | nan | 0.0001 | 0.0001 | 0.0000 | 0.0000 | 0.0000 |
| LEAR 56 | 0.9999 | nan | 0.3560 | 0.0000 | 0.0000 | 0.0000 |
| LEAR 84 | 0.9999 | 0.6440 | nan | 0.0000 | 0.0000 | 0.0000 |
| LEAR 1092 | 1.0000 | 1.0000 | 1.0000 | nan | 0.9084 | 0.0000 |
| LEAR 1456 | 1.0000 | 1.0000 | 1.0000 | 0.0916 | nan | 0.0000 |
| LEAR Ens. | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | nan |

## Published results quoted for reference (MAE)
```
{
 "source": "Lago et al. (2021), forecasts published in jeslago/epftoolbox",
 "MAE": {
  "LEAR Ensemble": 6.140060611263736,
  "DNN Ensemble": 5.869865859211076
 }
}
```

## Phase A: our DNNs
```
{
 "accuracy": {
  "DNN SF": {
   "MAE": 6.363357948946886,
   "RMSE": 16.884944129971398,
   "sMAPE_pct": 14.53028408958973,
   "rMAE": 0.7730434114793608
  },
  "DNN SF_DA": {
   "MAE": 6.2234268185096155,
   "RMSE": 16.533647058825274,
   "sMAPE_pct": 14.483525991156633,
   "rMAE": 0.7560440788450411
  },
  "DNN SF_SF": {
   "MAE": 6.338105046417125,
   "RMSE": 16.222911884037867,
   "sMAPE_pct": 14.988497400708258,
   "rMAE": 0.769975598843645
  },
  "DNN SF_SF_DA": {
   "MAE": 6.058942837969322,
   "RMSE": 15.909166126111218,
   "sMAPE_pct": 14.07543230839012,
   "rMAE": 0.7360619784397643
  },
  "DNN Ens.": {
   "MAE": 5.8510282735662775,
   "RMSE": 16.03231561822193,
   "sMAPE_pct": 13.346263345379478,
   "rMAE": 0.7108037758599495
  }
 },
 "tests": {
  "gw_p_dnn_better_than_lear": 2.8209988789384965e-08,
  "gw_p_lear_better_than_dnn": 1.0,
  "gw_p_dnn_better_than_naive": 0.0,
  "dm_p_dnn_better_than_lear": 8.46515080255017e-10,
  "dm_p_lear_better_than_dnn": 0.9999999991534849,
  "dm_p_dnn_better_than_naive": 0.0
 },
 "published": {
  "DNN SF MAE": 6.298735444282332,
  "DNN SF_DA MAE": 6.307692510410325,
  "DNN SF_SF MAE": 6.296795916515829,
  "DNN SF_SF_DA MAE": 6.067794724366603,
  "DNN Ens. MAE": 5.869865859211076,
  "mean abs gap of the ensemble to published": 0.8730507902159986,
  "gw_p_ours_better_than_published": 0.7144963396167451,
  "gw_p_published_better_than_ours": 1.0,
  "dm_p_ours_better_than_published": 0.21036333698878995,
  "dm_p_published_better_than_ours": 0.78963666301121
 },
 "training": {
  "trainings": 2912,
  "epochs_mean": 161.73626373626374,
  "cpu": [
   "x86_64"
  ],
  "machines": 1,
  "commits": [
   "d987d43"
  ],
  "tensorflow": [
   "2.21.0"
  ],
  "vcpu_hours": 191.921
 },
 "port_check": {
  "cases": 12,
  "all_ok": true,
  "max_abs_diff": 4.9874202545652224e-09,
  "tolerance": 1e-06
 }
}
```

## Phase B: 4-window LEAR on BE.csv + ENTSO-E data, 2017-01-01 to 2026-09-30
3523 of 3560 test days evaluated (days depending on a dropped day are not forecast).
```
{
 "mean price": 87.48431225754565,
 "negative hours %": 2.2613303056107483,
 "MAE naive": 21.865304694152712,
 "MAE LEAR 56": 16.496622976818998,
 "MAE LEAR 84": 16.35807855015848,
 "MAE LEAR 1092": 15.654617937186584,
 "MAE LEAR 1456": 15.545881458179581,
 "MAE LEAR ens.": 14.524510368838111,
 "RMSE LEAR ens.": 26.748271347395782,
 "sMAPE % LEAR ens.": 23.140402191882366,
 "MAE ens. / MAE naive": 0.6642720315131168,
 "gain vs naive (EUR per MWh)": 7.340794325314601,
 "gain vs naive %": 33.57279684868833,
 "GW p (ens. better than naive)": 0.0,
 "DM p (ens. better than naive)": 0.0
}
```

### Phase B: our DNNs
```
{
 "accuracy": {
  "DNN SF": {
   "MAE": 15.60525797593197,
   "RMSE": 28.2220179300338,
   "sMAPE_pct": 23.996444203660424,
   "rMAE": 0.7110260846479022
  },
  "DNN SF_DA": {
   "MAE": 15.647612000555869,
   "RMSE": 28.548384478199964,
   "sMAPE_pct": 23.87994432357617,
   "rMAE": 0.7129558711560047
  },
  "DNN SF_SF": {
   "MAE": 16.550675744216576,
   "RMSE": 30.69336792839569,
   "sMAPE_pct": 24.383182362383273,
   "rMAE": 0.7541023795208689
  },
  "DNN SF_SF_DA": {
   "MAE": 15.403107355355283,
   "RMSE": 28.808960036825567,
   "sMAPE_pct": 23.65740321513103,
   "rMAE": 0.7018154477920766
  },
  "DNN Ens.": {
   "MAE": 14.455521007335724,
   "RMSE": 26.586695135071725,
   "sMAPE_pct": 22.668777360726793,
   "rMAE": 0.6586403454043243
  }
 },
 "tests": {
  "gw_p_dnn_better_than_lear": 0.5115095265988246,
  "gw_p_lear_better_than_dnn": 1.0,
  "gw_p_dnn_better_than_naive": 0.0,
  "dm_p_dnn_better_than_lear": 0.24271303912290687,
  "dm_p_lear_better_than_dnn": 0.7572869608770931,
  "dm_p_dnn_better_than_naive": 0.0
 },
 "training": {
  "trainings": 14092,
  "epochs_mean": 148.544777178541,
  "cpu": [
   "x86_64"
  ],
  "machines": 1,
  "commits": [
   "4ee9d02",
   "d987d43"
  ],
  "tensorflow": [
   "2.21.0"
  ],
  "vcpu_hours": 885.2894444444445
 }
}
```

## Decision
```
{
 "rule": "LEAR ensemble if one-sided GW p < 0.05 vs naive on the phase B test",
 "gw_p": 0.0,
 "dm_p": 0.0,
 "deployed_model": "lear_ensemble",
 "recalibration": "daily, four windows (56, 84, 1092, 1456 days)",
 "fallback": "naive forecast when a day has no LEAR forecast"
}
```

## Quarter-hour products: error of a perfect hourly forecast
```
{
 "period": [
  "2025-10-01",
  "2026-09-30"
 ],
 "hours": 8760,
 "perfect_hourly_forecast_MAE": 7.910800228310502
}
```

## Load test of the containerised service
```
{
 "setup": {
  "image_id": "sha256:ed71ea3d0657",
  "image_size_MB": 1177.652727,
  "docker_version": "29.8.2",
  "docker_cpus": 8,
  "docker_memory_GB": 4.106604544,
  "host": "Darwin arm64",
  "duration_s": 30,
  "uvicorn_workers": 1
 },
 "scenarios": {
  "normal": {
   "health": {
    "status": "ok",
    "lear_forecasts": true,
    "prices": true,
    "first_day": "2019-01-01",
    "last_day": "2026-10-01"
   },
   "levels": [
    {
     "clients": 1,
     "requests": 10329,
     "throughput_rps": 344.26666829626356,
     "p50_ms": 2.8797499999200227,
     "p95_ms": 3.73961680015782,
     "p99_ms": 4.5182717604620795,
     "errors": 0,
     "fallback_share": 0.011133701229547875
    },
    {
     "clients": 10,
     "requests": 26546,
     "throughput_rps": 884.5666597509959,
     "p50_ms": 6.927645499672508,
     "p95_ms": 36.7481562498142,
     "p99_ms": 64.28669389970304,
     "errors": 0,
     "fallback_share": 0.013862728848037369
    },
    {
     "clients": 50,
     "requests": 16351,
     "throughput_rps": 543.8436677688172,
     "p50_ms": 61.40866599889705,
     "p95_ms": 271.1342295006034,
     "p99_ms": 429.17485399902944,
     "errors": 0,
     "fallback_share": 0.012476301143660938
    }
   ]
  },
  "degraded": {
   "health": {
    "status": "ok",
    "lear_forecasts": false,
    "prices": true,
    "first_day": "2019-01-01",
    "last_day": "2026-10-01"
   },
   "levels": [
    {
     "clients": 1,
     "requests": 10201,
     "throughput_rps": 340.01058143462024,
     "p50_ms": 2.8962500000488944,
     "p95_ms": 3.818541001237463,
     "p99_ms": 4.755917001602938,
     "errors": 0,
     "fallback_share": 1.0
    },
    {
     "clients": 10,
     "requests": 25967,
     "throughput_rps": 865.4047578309243,
     "p50_ms": 6.9147089998296,
     "p95_ms": 37.2968543002571,
     "p99_ms": 68.12812778010995,
     "errors": 0,
     "fallback_share": 1.0
    },
    {
     "clients": 50,
     "requests": 17191,
     "throughput_rps": 571.9394039001367,
     "p50_ms": 58.41095800133189,
     "p95_ms": 260.60318799954985,
     "p99_ms": 422.0693161001686,
     "errors": 0,
     "fallback_share": 1.0
    }
   ]
  }
 }
}
```

