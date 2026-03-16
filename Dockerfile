FROM python:3.10-slim

RUN apt-get update && apt-get install -y \
    build-essential libpq-dev postgresql-client gcc g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml .
RUN mkdir src && pip install --no-cache-dir --no-deps .
COPY . .
RUN pip install --no-cache-dir -e .

ENV PYTHONUNBUFFERED=1