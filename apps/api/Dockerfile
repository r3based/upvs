FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY apps/api/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir \
    --default-timeout=600 --retries 10 \
    --only-binary=:all: \
    -r /app/requirements.txt

COPY apps/api /app/apps/api
COPY scripts /app/scripts

ENV PYTHONPATH=/app

CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
