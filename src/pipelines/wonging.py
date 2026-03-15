from pathlib import Path
from .stream import Stream


class WongingAnomalyJob(Stream):
    def create_source_tables(self):
        self.create_bet_events_source(
            self.create_kafka_conn(group_id="flink-wonging-anomaly", subject="BetEvent")
        )

    def create_sink_table(self):
        self.create_anomaly_sink("wonging_score DOUBLE")

    def get_query_filename(self) -> str:
        return Path(__file__).with_suffix(".fql").name


def create_wonging_anomaly_job():
    job = WongingAnomalyJob(parallelism=4)
    job.run()


if __name__ == "__main__":
    create_wonging_anomaly_job()
