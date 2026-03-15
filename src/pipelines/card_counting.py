from pathlib import Path
from .stream import Stream


class CardCountingAnomalyJob(Stream):
    def create_source_tables(self):
        config = self.create_kafka_conn(
            group_id="flink-card-counting-anomaly", subject="BetEvent"
        )
        self.create_bet_events_source(config)

    def create_sink_table(self):
        self.create_anomaly_sink("correlation_score DOUBLE")

    def get_query_filename(self) -> str:
        return Path(__file__).with_suffix(".fql").name


def create_card_counting_anomaly_job():
    job = CardCountingAnomalyJob(parallelism=4)
    job.run()


if __name__ == "__main__":
    create_card_counting_anomaly_job()
