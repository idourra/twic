## =========================
## Stage 1: builder
## =========================
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps (build essentials if needed for faiss / numpy wheels)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

COPY pyproject.toml ./
COPY app ./app
COPY scripts ./scripts
COPY data ./data
COPY models ./models

# Instalación editable (sin extras dev en imagen final por ahora)
RUN pip install --upgrade pip && pip install .

## =========================
## Stage 2: runtime
## =========================
FROM python:3.11-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

# Copiamos solo runtime (site-packages desde builder)
COPY --from=builder /usr/local/lib/python3.11 /usr/local/lib/python3.11
COPY --from=builder /usr/local/bin /usr/local/bin

COPY app ./app
COPY data ./data
COPY models ./models
COPY scripts ./scripts
COPY pyproject.toml ./

# Create non-root user
RUN addgroup --system twic && adduser --system --ingroup twic twic \
    && chown -R twic:twic /app
USER twic

EXPOSE 8000

# Variables configurables
ENV MODELS_DIR=models \
    DATA_DIR=data \
    DEFAULT_LANG=es

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
