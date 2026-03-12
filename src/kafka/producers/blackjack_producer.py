from typing import List, Dict, Any
import logging
import json
from confluent_kafka import Producer
from confluent_kafka.schema_registry import SchemaRegistryClient, topic_record_subject_name_strategy
from confluent_kafka.schema_registry.avro import AvroSerializer
from confluent_kafka.serialization import StringSerializer, SerializationContext, MessageField

from blackjack.events import (
    Event,
    BetEvent,
    OutcomeEvent,
    ActionEvent,
    ShuffleEvent,
    SeatEvent,
    UnseatEvent,
    CardDealtEvent,
    RoundStartEvent,
    RoundEndEvent,
    PlayerStateEvent,
)

logger = logging.getLogger(__name__)

ANALYTICS_EVENTS = (
    BetEvent,
    OutcomeEvent,
    ActionEvent,
    ShuffleEvent,
    SeatEvent,
    UnseatEvent,
)
VISUALIZATION_EVENTS = (
    CardDealtEvent,
    RoundStartEvent,
    RoundEndEvent,
    PlayerStateEvent,
)


class BlackjackProducer:
    def __init__(
        self,
        bootstrap_servers: str = "localhost:9092",
        schema_registry_url: str = "http://localhost:8081",
        analytics_topic: str = "blackjack-analytics",
        visualization_topic: str = "blackjack-visualization",
    ):
        self.topics = {
            "analytics": analytics_topic,
            "visualization": visualization_topic
        }
        
        self.producer = Producer({"bootstrap.servers": bootstrap_servers, "acks": "all"})
        self.schema_client = SchemaRegistryClient({'url': schema_registry_url})
        self.key_serializer = StringSerializer('utf-8')
        self._serializers: Dict[type, AvroSerializer] = {}

    def _get_serializer(self, event_type: type) -> AvroSerializer:
        if event_type not in self._serializers:
            # Generate Avro schema with proper namespace
            schema_dict = event_type.avro_schema(namespace='com.tablewatch.blackjack')
            # AvroSerializer needs JSON string, not dict
            schema_str = json.dumps(schema_dict)
            self._serializers[event_type] = AvroSerializer(
                self.schema_client,
                schema_str,
                conf={
                    'subject.name.strategy': topic_record_subject_name_strategy
                }
            )
        return self._serializers[event_type]

    def send_event(self, event: Event) -> None:
        topic = self.topics["analytics"] if isinstance(event, ANALYTICS_EVENTS) else self.topics["visualization"]
        key = next((getattr(event, attr) for attr in ["player_id", "team_id", "round_id"] if getattr(event, attr, None)), event.table_id)

        serializer = self._get_serializer(type(event))
        key_bytes = self.key_serializer(key, SerializationContext(topic, MessageField.KEY))

        # Convert event to dict - use default mode (not json) to preserve datetime objects
        # Then convert datetime to microseconds for Avro timestamp-micros logical type
        event_dict = event.model_dump()
        if 'timestamp' in event_dict and event_dict['timestamp'] is not None:
            # Convert datetime to microseconds since epoch (Avro timestamp-micros)
            event_dict['timestamp'] = int(event_dict['timestamp'].timestamp() * 1_000_000)

        value_bytes = serializer(event_dict, SerializationContext(topic, MessageField.VALUE))

        self.producer.produce(
            topic=topic,
            key=key_bytes,
            value=value_bytes,
            on_delivery=lambda err, msg: print(f"Error: {err}") if err else None
        )

    def send_events(self, events: List[Event]) -> None:
        for event in events:
            self.send_event(event)
        self.producer.flush()
        
    def close(self) -> None:
        self.producer.flush()

    def __enter__(self): return self
    def __exit__(self, *args): self.producer.flush()