# WindScope API image.
# Build from the repository root so the validated dataset can be copied in:
#   docker build -f backend/Dockerfile -t windscope-api .
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    ENVIRONMENT=production \
    DATA_DIR=/app/data/processed \
    PORT=8000

WORKDIR /app

# System dependencies are limited to timezone data; the app itself is pure Python.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend/app /app/backend/app
COPY data/processed/windscope_january_2026.json.gz /app/data/processed/windscope_january_2026.json.gz

# Run as an unprivileged user.
RUN useradd --create-home --uid 10001 windscope \
    && chown -R windscope:windscope /app
USER windscope

WORKDIR /app/backend

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=3).status == 200 else 1)"

CMD ["sh", "-c", "python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
