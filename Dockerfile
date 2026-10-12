# Forecast service (src/be_power_forecast/api/app.py). The LEAR backtest forecasts (our own
# results) are copied into the image; the ENTSO-E prices are not (re-use terms): mount
# data/cache read-only at /data (prices_BE.parquet, written by scripts/build_phase_b.py).
#   docker build -t be-power-forecast .
#   docker run -p 8000:8000 -v "$PWD/data/cache:/data:ro" be-power-forecast
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    BE_FORECAST_DIR=/app/forecasts \
    BE_PRICE_PATH=/data/prices_BE.parquet

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install ".[api]" && rm -rf src
COPY results/forecasts/phase_b ./forecasts

RUN useradd --create-home --uid 10001 app
USER app

EXPOSE 8000
CMD ["uvicorn", "be_power_forecast.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
