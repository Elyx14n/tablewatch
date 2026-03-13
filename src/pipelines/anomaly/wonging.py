from pathlib import Path
from .base_anomaly_job import BaseAnomalyJob, bet_anomaly_sink_schema


class WongingAnomalyJob(BaseAnomalyJob):
    def create_source_tables(self):
        self.create_bet_events_source()

    def create_sink_table(self):
        self.create_anomaly_sink(bet_anomaly_sink_schema())

    def get_query_filename(self) -> str:
        return Path(__file__).with_suffix(".sql").name


def create_wonging_anomaly_job():
    job = WongingAnomalyJob(parallelism=4)
    job.run()


if __name__ == "__main__":
    create_wonging_anomaly_job()
