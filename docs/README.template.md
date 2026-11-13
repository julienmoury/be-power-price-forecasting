# Forecasting tomorrow's Belgian electricity prices

[![CI](https://github.com/julienmoury/be-power-price-forecasting/actions/workflows/ci.yml/badge.svg)](https://github.com/julienmoury/be-power-price-forecasting/actions/workflows/ci.yml)

Every day before noon, an auction sets the Belgian electricity price for each hour of the
next day. Producers, suppliers and battery operators all want to know these prices in
advance. In this project I took the reference benchmark of the field (Lago et al., 2021),
checked that I get the same results as the paper, and then ran it, unchanged, on the ten
years that followed, to see whether it still holds on today's market.

**[Live page](https://dkx1i5wqs8b2p.cloudfront.net/)**: the forecasts of every day since 1 October 2026, against
the realised prices, updated every evening. The forecasts are also served by a public API,
`https://ivqhqjlyjymcnufukn7vjp5mee0yezkr.lambda-url.eu-central-1.on.aws/` (`GET /health`, `POST /forecast`, `GET /forecasts`;
[schema](docs/openapi.json)).

## In short

- **The paper is reproduced.** On its test period (2015–2016), my LEAR ensemble has an
  error of {{accuracy/LEAR Ens./MAE}} EUR/MWh (paper: {{reproduction/LEAR Ensemble/MAE (published)}}) and
  my neural network ensemble {{dnn/accuracy/DNN Ens./MAE}} (paper: {{dnn/published/DNN Ens. MAE}}).
- **The models still work today.** From {{phase_b/test_period/0}} to {{phase_b/test_period/1}}, the LEAR
  ensemble makes {{phase_b/accuracy/gain vs naive %|.0f}} % less error than a naive forecast.
- **The neural network is no longer better.** It was clearly better in 2015–2016; on
  2017–2026 the two models are statistically tied ({{phase_b/dnn/accuracy/DNN Ens./MAE}} vs
  {{phase_b/accuracy/MAE LEAR ens.}} EUR/MWh).
- **A tuned LightGBM does not beat them.** Beyond the paper, I tuned a gradient-boosting
  challenger on 2015–2016 and tracked the {{phase_b/lgbm/tuning/configurations|d}} trials
  with MLflow. On 2017–2026 it beats the naive forecast but makes more error than both
  models of the paper ({{phase_b/lgbm/accuracy/MAE}} EUR/MWh).
- **Hourly forecasts have a floor.** Since October 2025 the market sets 96 quarter-hour
  prices a day; even a perfect hourly forecast would miss them by
  {{quarter_hour/perfect_hourly_forecast_MAE}} EUR/MWh on average.

## The models

- **Naive forecast**, the baseline any model has to beat: tomorrow looks like today
  (Monday and the weekend copy the same day of last week).
- **LEAR**: one linear regression per hour of the day. The inputs are the prices of the
  last days (d-1, d-2, d-3, d-7), the French load and generation forecasts (Belgium and
  France are coupled through the market) and the day of the week. A LASSO penalty keeps
  only the useful inputs. The model is re-estimated every day on four history lengths
  (56 days to 4 years), and the four forecasts are averaged.
- **DNN**: the paper's four small neural networks, with the settings published by the
  authors, retrained every day and averaged.

To compare two models I use the error in EUR/MWh (MAE) and the Giacomini-White test, which
tells whether one model is really better or just lucky on this sample.

## What I did

1. **Ported the code.** The paper's code no longer runs with recent
   libraries. I rewrote the parts I needed and checked them against the original code:
   same LEAR forecasts to 10⁻⁶ EUR/MWh, same DNN training to {{dnn/port_check/max_abs_diff|.0e}} EUR/MWh.
2. **Reproduced the paper** on its Belgian dataset (2011–2016).
3. **Extended it to today** with ENTSO-E data, from 2017 to September 2026: the 2022
   crisis, negative prices ({{phase_b/accuracy/negative hours %|.1f}} % of hours) and the switch to
   quarter-hours. Nothing was re-tuned.
4. **Made it run on its own.** Since 1 October 2026, the day after the backtest ends, a
   scheduled task on AWS (ECS Fargate) downloads the new data every evening, retrains the
   models, forecasts the next day and updates the live page (S3 and CloudFront). The errors
   since 1 October are computed in SQL (DuckDB). The infrastructure is in Terraform and
   deployed by GitHub Actions ([docs/aws.md](docs/aws.md)). A small API (FastAPI, in Docker,
   on AWS Lambda) serves the forecasts to my
   [storage project](https://github.com/julienmoury/be-storage-dispatch), which computes what
   they are worth to a battery.

## Results

**Paper's test period, {{test_period/0}} to {{test_period/1}} ({{n_days|d}} days)**

| Model | Error (MAE, EUR/MWh) | Paper |
|---|---:|---:|
| Naive | {{accuracy/Naive/MAE}} | —* |
| LEAR ensemble | {{accuracy/LEAR Ens./MAE}} | {{reproduction/LEAR Ensemble/MAE (published)}} |
| DNN ensemble | **{{dnn/accuracy/DNN Ens./MAE}}** | {{dnn/published/DNN Ens. MAE}} |

\* The Paper column is computed from the forecasts the paper publishes (Zenodo), LEAR and
DNN only: no naive forecast is published.

The LEAR beats the naive forecast by {{headline/ensemble_vs_naive_pct|.0f}} %, and the DNN beats the LEAR
(GW p {{dnn/tests/gw_p_dnn_better_than_lear|p}}), as in the paper.

**Today's market, {{phase_b/test_period/0}} to {{phase_b/test_period/1}} ({{phase_b/evaluated_days|d}} days)**

| Model | Error (MAE, EUR/MWh) |
|---|---:|
| Naive | {{phase_b/accuracy/MAE naive}} |
| LEAR ensemble | {{phase_b/accuracy/MAE LEAR ens.}} |
| DNN ensemble | {{phase_b/dnn/accuracy/DNN Ens./MAE}} |
| LightGBM (challenger, beyond the paper) | {{phase_b/lgbm/accuracy/MAE}} |

Errors are much larger than in 2015–2016 because prices are much more volatile, but both
models still beat the naive forecast by a third. Between the two, the test does not
separate them: for "the DNN is better", GW p {{phase_b/dnn/tests/gw_p_dnn_better_than_lear|p}}; for
"the LEAR is better", p {{phase_b/dnn/tests/gw_p_lear_better_than_dnn|p}}.

![Monthly error](results/figures/monthly_mae.png)

*Monthly error of each model; the LightGBM challenger (see below) runs on 2017–2026 only.*

Every single model (each history length, each network) is in
[`results/summary.md`](results/summary.md).

## Challenger beyond the paper: LightGBM

To see whether a popular modern model does better, I added a LightGBM challenger, kept
apart from the reproduction. It gets exactly the inputs of the LEAR and, like it, one
model per hour retrained every day on the past only.

**Tuning before the test.** I chose its settings on {{phase_b/lgbm/tuning/period/0}} to
{{phase_b/lgbm/tuning/period/1}} only, before the test period: {{phase_b/lgbm/tuning/configurations|d}}
configurations (history length, tree size, learning rate, number of trees), each backtested
with a weekly retraining and recorded as one MLflow run with its settings, its error and its
duration. The best one ({{phase_b/lgbm/tuning/best/calibration_window|d}} days of history,
{{phase_b/lgbm/tuning/best/num_leaves|d}} leaves, learning rate {{phase_b/lgbm/tuning/best/learning_rate|g}},
{{phase_b/lgbm/tuning/best/n_estimators|d}} trees) had an error of {{phase_b/lgbm/tuning/best/MAE}} EUR/MWh,
against {{phase_b/lgbm/tuning/worst_MAE}} for the worst. I froze it, then ran the 2017–2026
test once, with no re-tuning.

![MLflow comparison of the tuning runs](results/figures/mlflow_tuning.png)

*Each line is one configuration, coloured by its error: the longest history and the
slowest learning rate win.*

**Result: it loses.** On 2017–2026 it makes {{phase_b/lgbm/gain vs naive %|.0f}} % less
error than the naive forecast, but more than the LEAR ensemble
({{phase_b/lgbm/accuracy/MAE}} vs {{phase_b/accuracy/MAE LEAR ens.}} EUR/MWh) and the DNN
ensemble ({{phase_b/dnn/accuracy/DNN Ens./MAE}}). The GW test is clear: for "the LEAR is
better", p {{phase_b/lgbm/tests/gw_p_lear_better_than_lgbm|p}}; for "the DNN is better",
p {{phase_b/lgbm/tests/gw_p_dnn_better_than_lgbm|p}}. The gap is widest in the 2022 crisis
({{phase_b/lgbm/MAE by year/2022/LightGBM}} vs {{phase_b/lgbm/MAE by year/2022/LEAR ens.}} EUR/MWh
for the LEAR). A likely reason: a tree can only predict values close to those it saw in
training, so it cannot follow
prices that rise above their past range, while a linear model can. The yearly errors are
in [`results/summary.md`](results/summary.md). LightGBM is also in the live forecast.

## What I take away

- The simple linear model holds up remarkably well: ten years later, on a very different
  market, it is as good as the neural network, at a fraction of the cost.
- The DNN settings were tuned on 2011–2016 data. Re-tuning them on recent data might help
  it, but that would no longer be the paper's model.
- Reproducing a paper is harder than it looks: the public code does not give exactly the
  published LEAR forecasts day by day (the long windows match, the short ones do not), so
  I compare with the paper on overall errors.

## Limits

- **The forecast is made after the auction.** One input of the paper, the French
  generation forecast, is published after the noon deadline. The live forecast follows
  the paper, so it could not have been used to bid.
- **Hourly forecasts on a quarter-hour market** (see above).
- **Only France as a neighbour**, and no weather, gas price or Belgian wind and solar
  forecasts: these are not in the paper.
- ENTSO-E prices are not on its free re-use list, so no raw ENTSO-E data are in this
  repository; reproducing the extension needs your own ENTSO-E token. The live page shows
  realised prices from SMARD.de (CC BY 4.0).

## What I would do next

With the paper's inputs, neither the DNN nor LightGBM beats the linear model, so the next
gain is more likely to come from better inputs than from a more complex model. To turn this
into a forecast usable today, I would:

1. **Forecast before the auction from Belgian fundamentals**: Belgian load, wind and solar
   forecasts, weather and the gas price. Wind and solar push the price down and gas plants
   often set it (the merit order).
2. **Add the other coupled markets** (Netherlands, Germany), whose prices move with the
   Belgian one.
3. **Forecast the 96 quarter-hours directly.**
4. **Check what the model learned** (SHAP values): does it react to wind and gas as the
   merit order says it should?

Each new model would be compared with the LEAR ensemble on the same days, with the same
test.

## How it is organised

```
src/be_power_forecast/
  data/         ENTSO-E download, daylight-saving and quarter-hour handling
  models/       LEAR and DNN (adapted from the paper's code), LightGBM challenger
  evaluation/   error measures, Diebold-Mariano and Giacomini-White tests
  api/          FastAPI service, with the naive forecast as fallback
  live.py       daily forecast
  sql/          live errors in SQL (DuckDB), run by live_report.py
  cloud.py      S3 state of the AWS deployment
scripts/        backtests, LightGBM tuning, report, live forecast (aws_run.py: on AWS)
infra/          AWS infrastructure (Terraform), see docs/aws.md
tests/          unit tests and checks against the original code (run in CI)
```

The numbers of this README are read from [`results/metrics.json`](results/metrics.json)
by `scripts/make_report.py`, so the text cannot drift from the results.

## Reproduce

```bash
pip install -e ".[dev,api]"                 # Python 3.11–3.13
pytest -q                                   # tests, including the checks against the paper's code
export ENTSOE_API_KEY=...                   # your own token
python scripts/build_phase_b.py             # download ENTSO-E data
python scripts/run_experiments.py           # backtests on the paper's period (long)
pip install -e ".[experiments]"             # MLflow, for the LightGBM tuning
python scripts/tune_lgbm.py                 # tuning on 2015–2016, tracked in mlruns/ (long)
python scripts/run_experiments.py --phase B # backtests 2017–2026, LightGBM included (long)
python scripts/make_report.py               # metrics.json, figure, README
```

## Reference

- J. Lago, G. Marcjasz, B. De Schutter, R. Weron (2021). *Forecasting day-ahead
  electricity prices: A review of state-of-the-art algorithms, best practices and an
  open-access benchmark.* Applied Energy 293, 116983.
- Data: Zenodo record [4624805](https://zenodo.org/records/4624805), ENTSO-E Transparency
  Platform, SMARD.de.
