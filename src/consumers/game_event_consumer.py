import io
import json
import logging
import os
import struct
import time
from datetime import datetime, timezone

import fastavro
import psycopg2
import psycopg2.extras
from confluent_kafka import Consumer, KafkaError
from confluent_kafka.schema_registry import SchemaRegistryClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

TOPICS = [
    os.getenv("KAFKA_TOPIC", "blackjack"),
    os.getenv("BET_TOPIC", "bet_events"),
    os.getenv("OUTCOME_TOPIC", "outcome_events"),
    os.getenv("SEAT_TOPIC", "seat_events"),
]

SUIT_SYMBOLS = {"CLUBS": "♣", "DIAMONDS": "♦", "HEARTS": "♥", "SPADES": "♠"}

EVENT_TYPE_LABELS = {
    "bet": "BET",
    "card_dealt": "CARD",
    "action": "ACTION",
    "outcome": "OUTCOME",
    "round_start": "ROUND START",
    "round_end": "ROUND END",
    "seat": "WONGED IN",
    "unseat": "WONGED OUT",
}

INSERT_SQL = """
INSERT INTO game_events (event_id, event_time, table_id, round_id, event_type, player_id, summary, bankroll_after)
VALUES %s
ON CONFLICT (event_id, event_time) DO NOTHING
"""

BATCH_SIZE = 500
FLUSH_INTERVAL = 2.0

# High-volume events that flood the blackjack topic — skip them to keep up
_SKIP_EVENT_TYPES = {"card_dealt", "action"}


def _deserialize(schema_registry: SchemaRegistryClient, raw: bytes) -> dict:
    """Confluent wire format: 0x00 magic byte + 4-byte schema ID + avro payload."""
    if not raw or raw[0] != 0:
        raise ValueError(f"Unexpected magic byte: {raw[0] if raw else 'empty'}")
    schema_id = struct.unpack(">I", raw[1:5])[0]
    schema_str = schema_registry.get_schema(schema_id).schema_str
    parsed_schema = fastavro.parse_schema(json.loads(schema_str))
    return fastavro.schemaless_reader(io.BytesIO(raw[5:]), parsed_schema)


def _to_datetime(ts) -> datetime:
    if isinstance(ts, datetime):
        return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
    return datetime.fromtimestamp(ts / 1_000_000, tz=timezone.utc)


def _get_player_id(event: dict) -> str | None:
    if event.get("event_type") == "card_dealt":
        return event.get("recipient_id")  # "HOUSE" for dealer, player_id for players
    return event.get("player_id")


def _format_summary(event: dict) -> str:
    etype = event.get("event_type", "")

    if etype == "bet":
        return (
            f"Bet ${event.get('bet_amount', 0):.0f}"
            f"  (bankroll: ${event.get('bankroll_after', 0):.0f})"
        )
    if etype == "card_dealt":
        rank = event.get("card_rank", "?")
        suit = SUIT_SYMBOLS.get(event.get("card_suit", ""), "?")
        value = event.get("hand_value_after", "?")
        hidden = " [hole]" if event.get("is_hidden") else ""
        return f"{rank}{suit}{hidden}  →  hand: {value}"
    if etype == "action":
        return (
            f"{event.get('action', '?')}"
            f"  (hand: {event.get('player_hand_value', '?')}"
            f"  vs dealer: {event.get('dealer_upcard_value', '?')})"
        )
    if etype == "outcome":
        result = event.get("result", "?").upper()
        payout = event.get("payout", 0)
        sign = "+" if payout >= 0 else ""
        hand_val = event.get("player_hand_value")
        dealer_val = event.get("dealer_upcard_value")
        detail = f"  (hand: {hand_val} vs dealer: {dealer_val})" if hand_val and dealer_val else ""
        return f"{result}  {sign}${payout:.0f}{detail}"
    if etype == "round_start":
        n = len(event.get("active_player_ids") or [])
        return f"Round {event.get('round_number')} started  ({n} players)"
    if etype == "round_end":
        return f"Round {event.get('round_number')} ended"
    if etype == "seat":
        return f"Wonged in  (true count: {event.get('true_count', 0):.1f})"
    if etype == "unseat":
        return f"Wonged out  (true count: {event.get('true_count', 0):.1f})"
    return ""


def _connect_db() -> psycopg2.extensions.connection:
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
    schema_registry = SchemaRegistryClient(
        {"url": os.getenv("SCHEMA_REGISTRY_URL", "http://schema-registry:8081")}
    )
    consumer = Consumer(
        {
            "bootstrap.servers": os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092"),
            "group.id": "game-event-consumer",
            "auto.offset.reset": "latest",
            "enable.auto.commit": True,
        }
    )
    consumer.subscribe(TOPICS)
    logger.info(f"Subscribed to topics: {TOPICS}")

    db_conn = _connect_db()
    batch: list[tuple] = []
    last_flush = time.monotonic()

    try:
        while True:
            msg = consumer.poll(timeout=0.5)
            if msg is None:
                continue
            err = msg.error()
            if err:
                if err.code() != KafkaError._PARTITION_EOF:
                    logger.error(f"Kafka error: {msg.error()}")
            else:
                try:
                    val = msg.value()
                    assert val is not None
                    event = _deserialize(schema_registry, val)
                    etype = event.get("event_type", "")
                    if etype in _SKIP_EVENT_TYPES:
                        continue
                    batch.append((
                        event.get("event_id"),
                        _to_datetime(event["timestamp"]),
                        event.get("table_id"),
                        event.get("round_id"),
                        EVENT_TYPE_LABELS.get(etype, etype.upper()),
                        _get_player_id(event),
                        _format_summary(event),
                        event.get("bankroll_after") if etype == "bet" else None,
                    ))
                except Exception as e:
                    logger.warning(f"Failed to process message: {e}")

            now = time.monotonic()
            if batch and (len(batch) >= BATCH_SIZE or now - last_flush >= FLUSH_INTERVAL):
                try:
                    with db_conn.cursor() as cur:
                        psycopg2.extras.execute_values(cur, INSERT_SQL, batch)
                    db_conn.commit()
                    logger.info(f"Flushed {len(batch)} events to game_events")
                    batch.clear()
                    last_flush = now
                except Exception as e:
                    logger.error(f"DB insert failed: {e}")
                    db_conn.rollback()
                    try:
                        db_conn = _connect_db()
                    except Exception:
                        pass

    except KeyboardInterrupt:
        pass
    finally:
        if batch:
            try:
                with db_conn.cursor() as cur:
                    psycopg2.extras.execute_values(cur, INSERT_SQL, batch)
                db_conn.commit()
            except Exception:
                pass
        consumer.close()
        db_conn.close()
        logger.info("Consumer shut down")


if __name__ == "__main__":
    run()
