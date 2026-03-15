from dotenv import load_dotenv
import os

load_dotenv()

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC")
KAFKA_GROUP_ID = os.getenv("KAFKA_GROUP_ID")
SCHEMA_REGISTRY_URL = os.getenv("SCHEMA_REGISTRY_URL")

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

POSTGRES_CONN_CORRELATIONS = f"""
	'connector' = 'jdbc',
	'url' = '{POSTGRES_URL}',
	'table-name' = 'player_correlations',
	'username' = '{POSTGRES_USER}',
	'password' = '{POSTGRES_PASSWORD}',
	'driver' = 'org.postgresql.Driver'
"""

POSTGRES_CONN_DETECTED_TEAMS = f"""
	'connector' = 'jdbc',
	'url' = '{POSTGRES_URL}',
	'table-name' = 'detected_teams',
	'username' = '{POSTGRES_USER}',
	'password' = '{POSTGRES_PASSWORD}',
	'driver' = 'org.postgresql.Driver'
"""
