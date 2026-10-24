# syntax=docker/dockerfile:1
# Imagen única para API, UI e inicialización de datos (cambia solo el comando).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    COSCO_DB=/app/data/cosco.db

# libgomp1: requerida por lightgbm/catboost en la imagen slim
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Usuario sin privilegios
RUN useradd --create-home app && mkdir -p /app/data && chown -R app:app /app
USER app

EXPOSE 8000 8501
CMD ["uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "8000"]
