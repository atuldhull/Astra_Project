# ASTRA backend — minimal CPU-only image.
#
# For the GPU build (CUDA + TensorRT) we'd FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04
# and pip-install torch with cu124 index. That's deferred — this image
# is for the docker-compose.full.yml path where CPU inference is fine.

FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# OS deps for opencv + reportlab + psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 libsm6 libxext6 libxrender1 \
        libpq5 build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install requirements first for layer caching
COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip \
 && pip install -r /app/requirements.txt \
 && pip install torch --index-url https://download.pytorch.org/whl/cpu

COPY . /app

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=6 \
  CMD python -c "import httpx; httpx.get('http://localhost:8000/health').raise_for_status()" || exit 1

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
