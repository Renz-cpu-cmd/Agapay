FROM python:3.12-slim AS core

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt requirements-lock.txt ./
RUN python -m pip install --no-cache-dir -c requirements-lock.txt -r requirements.txt

COPY app ./app

RUN useradd --uid 10001 --create-home agapay && mkdir -p /var/lib/agapay && chown agapay:agapay /var/lib/agapay
USER agapay
EXPOSE 8000

CMD ["python", "-m", "app.serve_production"]

# Explicit research/development runtime. Never selected by the production entrypoint.
FROM core AS hybrid
USER root
COPY requirements-ml.txt requirements-hybrid.txt ./
RUN python -m pip install --no-cache-dir -c requirements-lock.txt -r requirements-hybrid.txt
USER agapay

# Optional, reviewed registry export. No ignored local data/ directory is copied.
# Build with --target forecast-artifact after creating forecast-release explicitly.
FROM core AS forecast-artifact
ARG FORECAST_MANIFEST_SHA256
COPY --chown=agapay:agapay forecast-release /opt/forecast-release
RUN python -m app.forecast_release --verify /opt/forecast-release --expected-manifest-sha256 "$FORECAST_MANIFEST_SHA256"

# Default docker build remains the core production feature profile.
FROM core AS production
