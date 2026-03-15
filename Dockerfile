FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    postgresql-client \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy the build system files first to leverage Docker cache
COPY pyproject.toml .
# We create a dummy src folder so pip can install dependencies without failing
RUN mkdir src && pip install --no-cache-dir .

# Now copy the actual source code
COPY . .

# Final install to ensure the actual code is linked
RUN pip install --no-cache-dir .

# Ensure Python doesn't buffer logs (critical for seeing Flink/Kafka output in Docker)
ENV PYTHONUNBUFFERED=1