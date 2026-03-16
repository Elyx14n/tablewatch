from pathlib import Path
from .stream import Stream


class BetSpreadAnomalyJob(Stream):
    def create_source_tables(self):
        config = self.create_kafka_conn(
            group_id="flink-bet-spread-anomaly", subject="BetEvent"
        )
        self.create_bet_events_source(config)

    def create_sink_table(self):
        self.create_anomaly_sink("bet_spread DOUBLE, z_score DOUBLE")

    def get_job_name(self) -> str:
        return "bet_spread"

    def get_query_filename(self) -> str:
        return Path(__file__).with_suffix(".fql").name


def create_bet_spread_anomaly_job():
    job = BetSpreadAnomalyJob(parallelism=4)
    job.run()


if __name__ == "__main__":
    create_bet_spread_anomaly_job()
