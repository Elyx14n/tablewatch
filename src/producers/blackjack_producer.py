from typing import List, Dict
import logging
import json
import os
from confluent_kafka import Producer
from confluent_kafka.schema_registry import SchemaRegistryClient, topic_record_subject_name_strategy  # type: ignore
from confluent_kafka.schema_registry.avro import AvroSerializer  # type: ignore
from confluent_kafka.serialization import StringSerializer, SerializationContext, MessageField  # type: ignore
from blackjack.events import (
    Event,
    BetEvent,
    OutcomeEvent,
    ActionEvent,
    SeatEvent,
    UnseatEvent,
    CardDealtEvent,
    RoundStartEvent,
    RoundEndEvent,
)

logger = logging.getLogger(__name__)

EVENTS = (
    BetEvent,
    OutcomeEvent,
    ActionEvent,
    SeatEvent,
    UnseatEvent,
    CardDealtEvent,
    RoundStartEvent,
    RoundEndEvent,
)


class BlackjackProducer:
    def __init__(
        self,
        bootstrap_servers: str,
        schema_registry_url: str,
        topic: str = "blackjack",
    ):
        self.topic = topic
        self.bet_topic = os.getenv("BET_TOPIC", "bet_events")
        self.outcome_topic = os.getenv("OUTCOME_TOPIC", "outcome_events")
        self.seat_topic = os.getenv("SEAT_TOPIC", "seat_events")
        self.producer = Producer(
            {
                "bootstrap.servers": bootstrap_servers,
                "acks": "all",
                "linger.ms": 10,
                "compression.type": "snappy",
                "batch.size": 16384,
            }
        )
        self.schema_client = SchemaRegistryClient({"url": schema_registry_url})
        self.key_serializer = StringSerializer("utf-8")
        self._serializers: Dict[type, AvroSerializer] = {}

    def _get_serializer(self, event_type: type) -> AvroSerializer:
        if event_type not in self._serializers:
            schema_dict = event_type.avro_schema(namespace="com.tablewatch.blackjack")
            schema_str = json.dumps(schema_dict)
            self._serializers[event_type] = AvroSerializer(
                self.schema_client,
                schema_str,
                conf={"subject.name.strategy": topic_record_subject_name_strategy},
            )
        return self._serializers[event_type]

    def _get_topic(self, event: Event) -> str:
        if isinstance(event, BetEvent):
            return self.bet_topic
        if isinstance(event, OutcomeEvent):
            return self.outcome_topic
        if isinstance(event, SeatEvent):
            return self.seat_topic
        return self.topic

    def send_event(self, event: Event) -> None:
        key = event.table_id
        topic = self._get_topic(event)

        serializer = self._get_serializer(type(event))
        key_bytes = self.key_serializer(
            key, SerializationContext(topic, MessageField.KEY)
        )

        event_dict = event.model_dump()
        if "timestamp" in event_dict and event_dict["timestamp"] is not None:
            # Convert datetime to microseconds since epoch (Avro timestamp-micros)
            event_dict["timestamp"] = int(
                event_dict["timestamp"].timestamp() * 1_000_000
            )

        value_bytes = serializer(
            event_dict, SerializationContext(topic, MessageField.VALUE)
        )

        self.producer.produce(
            topic=topic,
            key=key_bytes,
            value=value_bytes,
            on_delivery=lambda err, msg: print(f"Error: {err}") if err else None,
        )

    def send_events(self, events: List[Event]) -> None:
        for event in events:
            self.send_event(event)
        self.producer.poll(0)  # Trigger callbacks without blocking

    def close(self) -> None:
        self.producer.flush(timeout=30)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
