FROM python:3.12-slim

WORKDIR /srv

# DEV=1 (set by docker-compose.yml, never on Railway) adds pytest.
ARG DEV=0

# Country database for visits/signups/register (docker/fetch_geo.py; a failure doesn't fail the build).
COPY docker/fetch_geo.py /opt/geo/
RUN python /opt/geo/fetch_geo.py

COPY pyproject.toml ./
COPY app ./app
COPY seed ./seed
RUN pip install --no-cache-dir . && \
    if [ "$DEV" = "1" ]; then pip install --no-cache-dir ".[dev]"; fi

EXPOSE 8000
CMD uvicorn app.api.main:app --host 0.0.0.0 --port ${PORT:-8000}
