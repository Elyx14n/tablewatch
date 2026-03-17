import logging
import os
import time
import psycopg2
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

INTERVAL_SECONDS = 1800
ROOT = Path(__file__).resolve().parent.parent
SQL_PATH = ROOT / "db" / "queries" / "team_detection.sql"

def _connect() -> psycopg2.extensions.connection:
    for attempt in range(30):
        try:
            conn = psycopg2.connect(
                host=os.getenv("DB_HOST", "timescaledb"),
                dbname=os.getenv("DB_NAME", "tablewatch"),
                user=os.getenv("DB_USER", "tablewatch"),
                password=os.getenv("DB_PASSWORD", "tablewatch"),
                port=os.getenv("DB_PORT", "5432"),
            )
            logger.info("Connected to TimescaleDB")
            return conn
        except Exception as e:
            logger.warning(f"DB connection attempt {attempt + 1}/30: {e}")
            time.sleep(5)
    raise RuntimeError("Could not connect to TimescaleDB after 30 attempts")


def run():
    conn = _connect()
    while True:
        try:
            with conn.cursor() as cur:
                cur.execute(SQL_PATH.read_text())
                rows = cur.rowcount
            conn.commit()
            logger.info(f"Upserted {rows} detected teams")
        except Exception as e:
            logger.error(f"Team detection query failed: {e}")
            conn.rollback()
            try:
                conn = _connect()
            except Exception:
                pass
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    run()
