## =========================
## Stage 1: builder
## =========================
FROM python:3.11-slim AS builder

ARG PIP_INDEX_URL
ARG PIP_EXTRA_INDEX_URL
ARG PIP_TRUSTED_HOST
ARG GIT_SHA
ARG BUILD_DATE

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependencias del sistema (para compilación de wheels si hiciera falta)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Copiamos sólo metadata primero para maximizar caché de dependencias
COPY pyproject.toml ./

RUN pip install --upgrade pip setuptools wheel

# (Opcional) Si se requiere lock reproducible, introducir pip-compile aquí
# RUN pip install pip-tools && pip-compile --strip-extras -o requirements.lock
# RUN pip install -r requirements.lock

# Ahora copiamos el código fuente
COPY app ./app
COPY scripts ./scripts
COPY data ./data
COPY models ./models

# Instalación del paquete (editable no necesario en runtime, hacemos instalación normal)
RUN pip install .

## =========================
## Stage 2: runtime
## =========================
FROM python:3.11-slim AS runtime
ARG GIT_SHA
ARG BUILD_DATE
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    GIT_SHA=$GIT_SHA BUILD_DATE=$BUILD_DATE
WORKDIR /app

# Copiamos runtime (site-packages + binarios)
COPY --from=builder /usr/local/lib/python3.11 /usr/local/lib/python3.11
COPY --from=builder /usr/local/bin /usr/local/bin

# Código y artefactos (en caso de que se actualicen dinámicamente)
COPY app ./app
COPY data ./data
COPY models ./models
COPY scripts ./scripts
COPY pyproject.toml ./

# Etiquetas OCI para trazabilidad
LABEL org.opencontainers.image.revision=$GIT_SHA \
      org.opencontainers.image.created=$BUILD_DATE \
      org.opencontainers.image.source="https://github.com/idourra/twic"

# Usuario no root
RUN addgroup --system twic && adduser --system --ingroup twic twic \
    && chown -R twic:twic /app
USER twic

EXPOSE 8000

ENV MODELS_DIR=models \
    DATA_DIR=data \
    DEFAULT_LANG=es

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]