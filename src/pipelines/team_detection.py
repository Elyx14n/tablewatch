import logging
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

from .betting_volatility_correlation import create_betting_volatility_correlation_job
from .recursive_network_expansion import create_recursive_network_expansion_job
from .entity_resolution_clustering import create_entity_resolution_clustering_job

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class TeamDetectionDAG:
    def __init__(self):
        self.scheduler = BlockingScheduler()
        self.stage1_completed = False
        self.stage2_completed = False

    def stage_1_job(self):
        try:
            logger.info("=" * 60)
            logger.info("STAGE 1/3: Betting Velocity Correlation Analysis")
            logger.info("=" * 60)

            create_betting_volatility_correlation_job()

            self.stage1_completed = True
            logger.info("✓ Stage 1 completed successfully")

            self.scheduler.add_job(
                self.stage_2_job,
                "date",
                run_date=datetime.now().timestamp(),
                id="stage_2_triggered",
                replace_existing=True,
            )

        except Exception as e:
            logger.error(f"✗ Stage 1 failed: {e}", exc_info=True)
            self.stage1_completed = False

    def stage_2_job(self):
        try:
            logger.info("=" * 60)
            logger.info("STAGE 2/3: Recursive Network Expansion")
            logger.info("=" * 60)

            create_recursive_network_expansion_job()

            self.stage2_completed = True
            logger.info("✓ Stage 2 completed successfully")

            self.scheduler.add_job(
                self.stage_3_job,
                "date",
                run_date=datetime.now().timestamp(),
                id="stage_3_triggered",
                replace_existing=True,
            )

        except Exception as e:
            logger.error(f"✗ Stage 2 failed: {e}", exc_info=True)
            self.stage2_completed = False

    def stage_3_job(self):
        try:
            logger.info("=" * 60)
            logger.info("STAGE 3/3: Entity Resolution Clustering")
            logger.info("=" * 60)

            create_entity_resolution_clustering_job()

            logger.info("✓ Stage 3 completed successfully")
            logger.info("=" * 60)
            logger.info("🎉 TEAM DETECTION PIPELINE COMPLETED!")
            logger.info("=" * 60)

        except Exception as e:
            logger.error(f"✗ Stage 3 failed: {e}", exc_info=True)

    def job_listener(self, event):
        """Listen to job events for logging"""
        if event.exception:
            logger.error(f"Job {event.job_id} failed!")
        else:
            logger.info(f"Job {event.job_id} completed successfully")

    def start(self):
        logger.info("Starting Team Detection DAG Scheduler")
        self.scheduler.add_listener(
            self.job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR
        )
        self.scheduler.add_job(
            self.stage_1_job,
            CronTrigger.from_crontab("*/30 * * * *"),  # Every 30 mins
            id="stage_1_main",
            replace_existing=True,
        )

        logger.info("Scheduler configured. First run in progress...")
        self.stage_1_job()

        try:
            self.scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            logger.info("Scheduler shutting down...")
            self.scheduler.shutdown()


def run_team_detection_pipeline():
    dag = TeamDetectionDAG()
    dag.start()


if __name__ == "__main__":
    run_team_detection_pipeline()
