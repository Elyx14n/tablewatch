from abc import ABC, abstractmethod
from pathlib import Path
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.table import StreamTableEnvironment, EnvironmentSettings
from .constants import *

_SUBJECT_TOPIC = {
    "BetEvent": BET_TOPIC,
    "OutcomeEvent": OUTCOME_TOPIC,
}

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
        self.table_env.get_config().set("pipeline.name", self.get_job_name())
        self.table_env.get_config().set("restart-strategy", "fixed-delay")
        self.table_env.get_config().set("restart-strategy.fixed-delay.attempts", "10")
        self.table_env.get_config().set("restart-strategy.fixed-delay.delay", "15 s")


    def to_data_stream(self, table_name: str):
        assert self.table_env is not None
        table = self.table_env.from_path(table_name)
        return self.table_env.to_data_stream(table)

    def create_bet_events_source(self, conn_config):
        assert self.table_env is not None
        self.table_env.execute_sql(
            f"""
            CREATE TABLE bet_events (
                event_id STRING NOT NULL,
                `timestamp` BIGINT NOT NULL,
                table_id STRING NOT NULL,
                round_id STRING NOT NULL,
                player_id STRING NOT NULL,
                team_id STRING,
                bet_amount DOUBLE NOT NULL,
                bankroll_after DOUBLE NOT NULL,
                true_count DOUBLE NOT NULL,
                cards_remaining BIGINT NOT NULL,
                is_shuffle BOOLEAN NOT NULL,
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
                event_id STRING NOT NULL,
                `timestamp` BIGINT NOT NULL,
                table_id STRING NOT NULL,
                round_id STRING NOT NULL,
                player_id STRING NOT NULL,
                `result` STRING NOT NULL,
                payout DOUBLE NOT NULL,
                player_hand_value BIGINT,
                dealer_upcard_value BIGINT,
                bankroll_after DOUBLE NOT NULL,
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
                PRIMARY KEY (player_id, anomaly_type, anomaly_detected_at) NOT ENFORCED
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
        topic = _SUBJECT_TOPIC.get(subject, KAFKA_TOPIC)
        return f"""
            'connector' = 'kafka',
            'topic' = '{topic}',
            'properties.bootstrap.servers' = '{KAFKA_BOOTSTRAP_SERVERS}',
            'properties.group.id' = '{group_id}',
            'scan.startup.mode' = 'latest-offset',
            'format' = 'avro-confluent',
            'avro-confluent.url' = '{SCHEMA_REGISTRY_URL}',
            'avro-confluent.schema-registry.subject' = '{topic}-com.tablewatch.blackjack.{subject}',
            'properties.request.timeout.ms' = '60000',
            'properties.session.timeout.ms' = '45000',
            'properties.heartbeat.interval.ms' = '3000'
            {extra_fields}
        """

    @abstractmethod
    def create_source_tables(self):
        pass

    @abstractmethod
    def create_sink_table(self):
        pass

    @abstractmethod
    def get_job_name(self) -> str:
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
        return result
