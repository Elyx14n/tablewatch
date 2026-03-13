from dotenv import load_dotenv
import os

load_dotenv()

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC")
KAFKA_GROUP_ID = os.getenv("KAFKA_GROUP_ID")
SCHEMA_REGISTRY_URL = os.getenv("SCHEMA_REGISTRY_URL")
KAFKA_CONN_BET_SPREAD = f"""
    'connector' = 'kafka',
    'topic' = '{KAFKA_TOPIC}',
    'properties.bootstrap.servers' = '{KAFKA_BOOTSTRAP_SERVERS}',
    'properties.group.id' = 'flink-bet-spread-anomaly',
    'format' = 'avro-confluent',
    'avro-confluent.url' = '{SCHEMA_REGISTRY_URL}',
    'avro-confluent.schema-registry.subject' = 'blackjack-com.tablewatch.blackjack.BetEvent'
"""

POSTGRES_URL = os.getenv("POSTGRES_URL")
POSTGRES_USER = os.getenv("POSTGRES_USER")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
POSTGRES_CONN_ANOMALY = f"""
	'connector' = 'jdbc',
	'url' = '{POSTGRES_URL}',
	'table-name' = 'player_anomalies',
	'username' = '{POSTGRES_USER}',
	'password' = '{POSTGRES_PASSWORD}',
	'driver' = 'org.postgresql.Driver'
"""

KAFKA_CONN_WIN_RATE = f"""
	'connector' = 'kafka',
	'topic' = '{KAFKA_TOPIC}',
	'properties.bootstrap.servers' = '{KAFKA_BOOTSTRAP_SERVERS}',
	'properties.group.id' = 'flink-win-rate-anomaly',
	'scan.startup.mode' = 'latest-offset',
	'format' = 'avro-confluent',
	'avro-confluent.url' = '{SCHEMA_REGISTRY_URL}',
	'avro-confluent.schema-registry.subject' = 'blackjack-com.tablewatch.blackjack.OutcomeEvent'
"""

POSTGRES_CONN_CORRELATIONS = f"""
	'connector' = 'jdbc',
	'url' = '{POSTGRES_URL}',
	'table-name' = 'player_correlations',
	'username' = '{POSTGRES_USER}',
	'password' = '{POSTGRES_PASSWORD}',
	'driver' = 'org.postgresql.Driver'
"""