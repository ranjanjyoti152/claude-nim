FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 8787

# GATEWAY_PORT is read from the environment at runtime; default 8787.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${GATEWAY_PORT:-8787}"]
