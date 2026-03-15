from pathlib import Path
from .stream import Stream


class BettingVolatilityCorrelationJob(Stream):
    def create_source_tables(self):
        config = self.create_kafka_conn(
            group_id="flink-bet-volatility-job", subject="BetEvent"
        )
        self.create_bet_events_source(conn_config=config)

    def create_sink_table(self):
        self.create_correlation_sink(
            """player_id_1 STRING,
                player_id_2 STRING,
                correlation DOUBLE,
                window_end TIMESTAMP(3),
                is_actual_team BOOLEAN,
                WATERMARK FOR window_end AS window_end - INTERVAL '5' SECOND"""
        )

    def get_query_filename(self) -> str:
        return Path(__file__).with_suffix(".fql").name


def create_betting_volatility_correlation_job():
    job = BettingVolatilityCorrelationJob(parallelism=4)
    job.run()


if __name__ == "__main__":
    create_betting_volatility_correlation_job()
