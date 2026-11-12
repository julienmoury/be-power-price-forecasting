# One image for the two jobs of the project, so that what runs every morning is what is
# tested:
# * the forecast service (src/be_power_forecast/api/app.py), the default command. The
#   backtest and live forecasts (our own results) are copied into the image; the ENTSO-E
#   prices are not (re-use terms): mount data/cache read-only at /data (prices_BE.parquet,
#   written by scripts/build_phase_b.py) for the naive fallback.
#     docker build -t be-power-forecast .
#     docker run -p 8000:8000 -v "$PWD/data/cache:/data:ro" be-power-forecast
# * the daily live forecast, run on the mounted repository:
#     docker run -v "$PWD:/repo" -e BE_REPO_ROOT=/repo -e ENTSOE_API_KEY \
#       be-power-forecast python scripts/live_forecast.py
# On AWS (docs/aws.md) the same image runs the live forecast on ECS Fargate
# (python scripts/aws_run.py: S3 in and out) and the forecast service on Lambda
# (python -m be_power_forecast.cloud, behind the AWS Lambda Web Adapter, an extension that
# only starts on Lambda).
FROM python:3.11-slim
# OpenMP runtime of LightGBM.
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:1.1.0 /lambda-adapter /opt/extensions/lambda-adapter

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    MPLCONFIGDIR=/tmp/matplotlib \
    BE_FORECAST_DIR=/app/forecasts \
    BE_PRICE_PATH=/data/prices_BE.parquet \
    BE_LIVE_PATH=/app/live/forecasts.csv \
    BE_DNN_LIVE_PATH=/app/live/dnn_forecasts.csv \
    BE_LGBM_LIVE_PATH=/app/live/lgbm_forecasts.csv

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install ".[api,aws]" && rm -rf src
COPY scripts/live_forecast.py scripts/run_dnn.py scripts/aws_run.py ./scripts/
COPY data/raw ./data/raw
COPY results/forecasts/phase_b ./forecasts
COPY results/forecasts/live ./live

RUN useradd --create-home --uid 10001 app
USER app

EXPOSE 8000
CMD ["uvicorn", "be_power_forecast.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
