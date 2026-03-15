from pathlib import Path
from .stream import Stream


class BetRateOfChangeAnomalyJob(Stream):
    def create_source_tables(self):
        config = self.create_kafka_conn(
            group_id="flink-bet-rate-of-change-anomaly", subject="BetEvent"
        )
        self.create_bet_events_source(config)

    def create_sink_table(self):
        self.create_anomaly_sink("bet_change_rate DOUBLE, z_score DOUBLE")

    def get_query_filename(self) -> str:
        return Path(__file__).with_suffix(".fql").name


def create_bet_rate_of_change_anomaly_job():
    job = BetRateOfChangeAnomalyJob(parallelism=4)
    job.run()


if __name__ == "__main__":
    create_bet_rate_of_change_anomaly_job()
