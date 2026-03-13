from abc import ABC, abstractmethod
from pathlib import Path
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.table import StreamTableEnvironment, EnvironmentSettings
from ..constants import (
    KAFKA_CONN_BET_SPREAD,
    KAFKA_CONN_WIN_RATE,
    POSTGRES_CONN_ANOMALY,
    POSTGRES_CONN_CORRELATIONS
)

ROOT = Path(__file__).resolve().parent.parent


class BaseAnomalyJob(ABC):
    def __init__(self, parallelism: int = 4):
        self.parallelism = parallelism
        self.env = None
        self.table_env = None

    def setup_environment(self):
        self.env = StreamExecutionEnvironment.get_execution_environment()
        self.env.set_parallelism(self.parallelism)

        settings = EnvironmentSettings.new_instance().in_streaming_mode().build()
        self.table_env = StreamTableEnvironment.create(self.env, settings)

    def create_bet_events_source(self):
        assert self.table_env is not None
        self.table_env.execute_sql(f"""
            CREATE TABLE bet_events (
                event_id STRING,
                timestamp BIGINT,
                table_id STRING,
                round_id STRING,
                player_id STRING,
                team_id STRING,
                bet_amount DOUBLE,
                bankroll_after DOUBLE,
                true_count DOUBLE,
                cards_remaining INT,
                event_time AS TO_TIMESTAMP(FROM_UNIXTIME(timestamp / 1000000)),
                WATERMARK FOR event_time AS event_time - INTERVAL '5' SECOND
            ) WITH ({KAFKA_CONN_BET_SPREAD})
        """)

    def create_outcome_events_source(self):
        assert self.table_env is not None
        self.table_env.execute_sql(f"""
            CREATE TABLE outcome_events (
                event_id STRING,
                timestamp BIGINT,
                table_id STRING,
                round_id STRING,
                player_id STRING,
                result STRING,
                payout DOUBLE,
                player_hand_value INT,
                dealer_upcard_value INT,
                bankroll_after DOUBLE,
                event_time AS TO_TIMESTAMP(FROM_UNIXTIME(timestamp / 1000000)),
                WATERMARK FOR event_time AS event_time - INTERVAL '5' SECOND
            ) WITH ({KAFKA_CONN_WIN_RATE})
        """)

    def create_anomaly_sink(self, schema_fields: str):
        assert self.table_env is not None
        self.table_env.execute_sql(f"""
            CREATE TABLE player_anomalies (
                player_id STRING,
                anomaly_type STRING,
                anomaly_confidence DOUBLE,
                anomaly_detected_at TIMESTAMP(3),
                {schema_fields},
                PRIMARY KEY (player_id, anomaly_detected_at) NOT ENFORCED
            ) WITH ({POSTGRES_CONN_ANOMALY})
        """)

    def create_correlation_sink(self, schema_fields: str):
        assert self.table_env is not None
        self.table_env.execute_sql(f"""
            CREATE TABLE player_correlations (
                {schema_fields},
                PRIMARY KEY (player_id_1, player_id_2, window_end) NOT ENFORCED
            ) WITH ({POSTGRES_CONN_CORRELATIONS})
        """)

    def load_sql_query(self) -> str:
        job_file = Path(self.__class__.__module__.replace(".", "/") + ".py")
        filename = Path(job_file).with_suffix(".sql").name
        sql_path = ROOT / "db" / "queries" / "anomaly" / filename
        return sql_path.read_text()

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
        query = self.load_sql_query()
        assert self.table_env is not None
        self.table_env.execute_sql(query)


def bet_anomaly_sink_schema() -> str:
    return "bet_spread DOUBLE, z_score DOUBLE"


def win_rate_anomaly_sink_schema() -> str:
    return "win_rate DOUBLE, q1 DOUBLE, q3 DOUBLE, iqr DOUBLE"


def correlation_sink_schema() -> str:
    return "player_id_1 STRING, player_id_2 STRING, correlation DOUBLE, window_end TIMESTAMP(3), correlation_level STRING, is_actual_team BOOLEAN"
