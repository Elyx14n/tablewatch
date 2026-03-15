from pathlib import Path
from .stream import Stream
from .constants import POSTGRES_CONN_CORRELATIONS, POSTGRES_CONN_ANOMALY


class EntityResolutionClusteringJob(Stream):
    def create_source_tables(self):
        assert self.table_env is not None
        self.table_env.execute_sql(
            f"""
            CREATE TABLE player_correlations (
                player_id_1 STRING,
                player_id_2 STRING,
                correlation DOUBLE,
                window_end TIMESTAMP(3),
                is_actual_team BOOLEAN,
                WATERMARK FOR window_end AS window_end - INTERVAL '5' SECOND
            ) WITH ({POSTGRES_CONN_CORRELATIONS})
        """
        )

        self.table_env.execute_sql(
            f"""
            CREATE TABLE player_anomalies (
                player_id STRING,
                anomaly_type STRING,
                anomaly_confidence DOUBLE,
                anomaly_detected_at TIMESTAMP(3),
                WATERMARK FOR anomaly_detected_at AS anomaly_detected_at - INTERVAL '5' SECOND
            ) WITH ({POSTGRES_CONN_ANOMALY})
        """
        )

    def create_sink_table(self):
        self.create_detected_teams_sink()

    def get_query_filename(self) -> str:
        return Path(__file__).with_suffix(".fql").name


def create_entity_resolution_clustering_job():
    job = EntityResolutionClusteringJob(parallelism=4)
    job.run()


if __name__ == "__main__":
    create_entity_resolution_clustering_job()
