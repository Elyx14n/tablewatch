FROM python:3.10-slim

RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    postgresql-client \
    gcc \
    g++ \
    default-jre-headless \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Set JAVA_HOME for PyFlink (automatically set by default-jre)
ENV JAVA_HOME=/usr/lib/jvm/default-java

WORKDIR /app

# Download connector JARs only - core Flink JARs come from PyFlink package
RUN mkdir -p /opt/flink/lib && \
    wget -q -P /opt/flink/lib https://repo1.maven.org/maven2/org/apache/flink/flink-sql-connector-kafka/3.1.0-1.18/flink-sql-connector-kafka-3.1.0-1.18.jar && \
    wget -q -P /opt/flink/lib https://repo1.maven.org/maven2/org/apache/flink/flink-sql-avro-confluent-registry/1.18.0/flink-sql-avro-confluent-registry-1.18.0.jar && \
    wget -q -P /opt/flink/lib https://repo1.maven.org/maven2/org/apache/flink/flink-connector-jdbc/3.2.0-1.18/flink-connector-jdbc-3.2.0-1.18.jar && \
    wget -q -P /opt/flink/lib https://jdbc.postgresql.org/download/postgresql-42.7.1.jar

# Copy the build system files first to leverage Docker cache
COPY pyproject.toml .
# We create a dummy src folder so pip can install dependencies without failing
RUN mkdir src && pip install --no-cache-dir .

# Now copy the actual source code
COPY . .

# Final install to ensure the actual code is linked
RUN pip install --no-cache-dir -e .

# Ensure Python doesn't buffer logs (critical for seeing Flink/Kafka output in Docker)
ENV PYTHONUNBUFFERED=1