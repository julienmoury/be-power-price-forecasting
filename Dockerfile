# One image for the two jobs of the project, so that what runs every morning is what is
# tested:
# * the forecast service (src/be_power_forecast/api/app.py), the default command. The LEAR
#   backtest and live forecasts (our own results) are copied into the image; the ENTSO-E
#   prices are not (re-use terms): mount data/cache read-only at /data (prices_BE.parquet,
#   written by scripts/build_phase_b.py) for the naive fallback.
#     docker build -t be-power-forecast .
#     docker run -p 8000:8000 -v "$PWD/data/cache:/data:ro" be-power-forecast
# * the daily live forecast (.github/workflows/live.yml), run on the mounted repository:
#     docker run -v "$PWD:/repo" -e BE_REPO_ROOT=/repo -e ENTSOE_API_KEY \
#       be-power-forecast python scripts/live_forecast.py
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    MPLCONFIGDIR=/tmp/matplotlib \
    BE_FORECAST_DIR=/app/forecasts \
    BE_PRICE_PATH=/data/prices_BE.parquet \
    BE_LIVE_PATH=/app/live/forecasts.csv \
    BE_DNN_LIVE_PATH=/app/live/dnn_forecasts.csv

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install ".[api]" && rm -rf src
COPY scripts/live_forecast.py scripts/run_dnn.py ./scripts/
COPY results/forecasts/phase_b ./forecasts
COPY results/forecasts/live ./live

RUN useradd --create-home --uid 10001 app
USER app

EXPOSE 8000
CMD ["uvicorn", "be_power_forecast.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
