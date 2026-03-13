from pathlib import Path
from .base_anomaly_job import BaseAnomalyJob, correlation_sink_schema


class TeamCorrelationPrefilterJob(BaseAnomalyJob):
    def create_source_tables(self):
        self.create_bet_events_source()

    def create_sink_table(self):
        self.create_correlation_sink(correlation_sink_schema())

    def get_query_filename(self) -> str:
        return Path(__file__).with_suffix(".sql").name


def create_team_correlation_prefilter_job():
    job = TeamCorrelationPrefilterJob(parallelism=4)
    job.run()


if __name__ == "__main__":
    create_team_correlation_prefilter_job()
