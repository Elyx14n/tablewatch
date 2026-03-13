from pathlib import Path
from .base_anomaly_job import BaseAnomalyJob, win_rate_anomaly_sink_schema


class WinRateAnomalyJob(BaseAnomalyJob):
    def create_source_tables(self):
        self.create_outcome_events_source()

    def create_sink_table(self):
        self.create_anomaly_sink(win_rate_anomaly_sink_schema())

    def get_query_filename(self) -> str:
        return Path(__file__).with_suffix(".sql").name


def create_win_rate_job():
    job = WinRateAnomalyJob(parallelism=4)
    job.run()


if __name__ == "__main__":
    create_win_rate_job()