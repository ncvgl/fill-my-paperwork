# Minimal container for FastAPI + static UI
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

# Copy source
COPY . ./playground

# Env defaults (overridable)
ENV GCP_LOCATION=europe-west9

EXPOSE 8080

CMD ["uvicorn", "playground.fastapi_server:app", "--host", "0.0.0.0", "--port", "8080"]
