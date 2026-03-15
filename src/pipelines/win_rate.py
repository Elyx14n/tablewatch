from pathlib import Path
from .stream import Stream

class WinRateAnomalyJob(Stream):
    def create_source_tables(self):
        self.create_outcome_events_source(
            self.create_kafka_conn(
                group_id="flink-win-rate-anomaly",
                subject="OutcomeEvent",
                extra_fields=""",'scan.startup.mode' = 'latest-offset'""",
            )
        )

    def create_sink_table(self):
        self.create_anomaly_sink("win_rate DOUBLE, q1 DOUBLE, q3 DOUBLE, iqr DOUBLE")

    def get_query_filename(self) -> str:
        return Path(__file__).with_suffix(".fql").name


def create_win_rate_job():
    job = WinRateAnomalyJob(parallelism=4)
    job.run()


if __name__ == "__main__":
    create_win_rate_job()
