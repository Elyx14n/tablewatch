from abc import ABC, abstractmethod
from pathlib import Path
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.table import StreamTableEnvironment, EnvironmentSettings
from .constants import *

ROOT = Path(__file__).resolve().parent


class Stream(ABC):
    def __init__(self, parallelism: int = 4):
        self.parallelism = parallelism
        self.env = None
        self.table_env = None

    def setup_environment(self):
        self.env = StreamExecutionEnvironment.get_execution_environment()
        self.env.set_parallelism(self.parallelism)

        settings = EnvironmentSettings.new_instance().in_streaming_mode().build()
        self.table_env = StreamTableEnvironment.create(self.env, settings)

        # Connector JARs only - using JDBC 3.2.0 which supports SinkV2 API
        jar_files = [
            "file:///opt/flink/lib/flink-sql-connector-kafka-3.1.0-1.18.jar",
            "file:///opt/flink/lib/flink-sql-avro-confluent-registry-1.18.0.jar",
            "file:///opt/flink/lib/flink-connector-jdbc-3.2.0-1.18.jar",
            "file:///opt/flink/lib/postgresql-42.7.1.jar",
        ]
        self.table_env.get_config().get_configuration().set_string(
            "pipeline.jars",
            ";".join(jar_files)
        )

    def to_data_stream(self, table_name: str):
        assert self.table_env is not None
        table = self.table_env.from_path(table_name)
        return self.table_env.to_data_stream(table)

    def create_bet_events_source(self, conn_config):
        assert self.table_env is not None
        self.table_env.execute_sql(
            f"""
            CREATE TABLE bet_events (
                event_id STRING,
                `timestamp` BIGINT,
                table_id STRING,
                round_id STRING,
                player_id STRING,
                team_id STRING,
                bet_amount DOUBLE,
                bankroll_after DOUBLE,
                true_count DOUBLE,
                cards_remaining INT,
                is_shuffle BOOLEAN,
                event_time AS TO_TIMESTAMP(FROM_UNIXTIME(`timestamp` / 1000000)),
                WATERMARK FOR event_time AS event_time - INTERVAL '5' SECOND
            ) WITH ({conn_config})
        """
        )

    def create_outcome_events_source(self, conn_config):
        assert self.table_env is not None
        self.table_env.execute_sql(
            f"""
            CREATE TABLE outcome_events (
                event_id STRING,
                `timestamp` BIGINT,
                table_id STRING,
                round_id STRING,
                player_id STRING,
                `result` STRING,
                payout DOUBLE,
                player_hand_value INT,
                dealer_upcard_value INT,
                bankroll_after DOUBLE,
                event_time AS TO_TIMESTAMP(FROM_UNIXTIME(`timestamp` / 1000000)),
                WATERMARK FOR event_time AS event_time - INTERVAL '5' SECOND
            ) WITH ({conn_config})
        """
        )

    def create_anomaly_sink(self, schema_fields: str):
        assert self.table_env is not None
        self.table_env.execute_sql(
            f"""
            CREATE TABLE player_anomalies (
                player_id STRING,
                anomaly_type STRING,
                anomaly_confidence DOUBLE,
                anomaly_detected_at TIMESTAMP(3),
                {schema_fields},
                PRIMARY KEY (player_id, anomaly_detected_at) NOT ENFORCED
            ) WITH ({POSTGRES_CONN_ANOMALY})
        """
        )

    def create_correlation_sink(self, schema_fields: str):
        assert self.table_env is not None
        self.table_env.execute_sql(
            f"""
            CREATE TABLE player_correlations (
                {schema_fields},
                PRIMARY KEY (player_id_1, player_id_2, window_end) NOT ENFORCED
            ) WITH ({POSTGRES_CONN_CORRELATIONS})
        """
        )

    def create_detected_teams_sink(self):
        assert self.table_env is not None
        self.table_env.execute_sql(
            f"""
            CREATE TABLE detected_teams (
                detected_team_id STRING,
                member_count INT,
                team_correlation DOUBLE,
                detected_at TIMESTAMP(3),
                team_name STRING,
                player_ids ARRAY<STRING>,
                PRIMARY KEY (detected_team_id) NOT ENFORCED
            ) WITH ({POSTGRES_CONN_DETECTED_TEAMS})
        """
        )

    def load_sql_query(self) -> str:
        filename = self.get_query_filename()
        sql_path = ROOT.parent / "db" / "queries" / filename
        return sql_path.read_text()

    def create_kafka_conn(self, group_id, subject, extra_fields = "") -> str:
        return f"""
            'connector' = 'kafka',
            'topic' = '{KAFKA_TOPIC}',
            'properties.bootstrap.servers' = '{KAFKA_BOOTSTRAP_SERVERS}',
            'properties.group.id' = '{group_id}',
            'format' = 'avro-confluent',
            'avro-confluent.url' = '{SCHEMA_REGISTRY_URL}',
            'avro-confluent.schema-registry.subject' = 'blackjack-com.tablewatch.blackjack.{subject}'
            {extra_fields}
        """

    @abstractmethod
    def create_source_tables(self):
        pass

    @abstractmethod
    def create_sink_table(self):
        pass

    @abstractmethod
    def get_query_filename(self) -> str:
        pass

    def run(self):
        self.setup_environment()
        self.create_source_tables()
        self.create_sink_table()
        assert self.table_env is not None
        result = self.table_env.execute_sql(self.load_sql_query())
        result.wait()
        return result
