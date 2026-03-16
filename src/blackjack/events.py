import uuid
from datetime import datetime, timezone
from pydantic import ConfigDict, Field
from typing import Optional, Literal
from enum import Enum
from pydantic_avro.to_avro.base import AvroBase


class EventType(str, Enum):
    BET = "bet"
    OUTCOME = "outcome"
    ACTION = "action"
    SHUFFLE = "shuffle"
    SEAT = "seat"
    UNSEAT = "unseat"
    CARD_DEALT = "card_dealt"
    PLAYER_STATE = "player_state"
    ROUND_START = "round_start"
    ROUND_END = "round_end"


class Result(str, Enum):
    WIN = "win"
    LOSS = "loss"
    PUSH = "push"
    BJ = "blackjack"
    BUST = "bust"
    SURRENDER = "surrender"


class Event(AvroBase):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    table_id: str
    round_id: str
    model_config = ConfigDict(frozen=True)


class PlayerStateEvent(Event):
    event_type: Literal[EventType.PLAYER_STATE] = EventType.PLAYER_STATE
    player_id: str
    team_id: Optional[str] = None
    bankroll: float
    net_profit: float
    total_hands: int
    hands_won: int
    hands_lost: int
    hands_pushed: int
    total_wagered: float
    win_rate: float


class BetEvent(Event):
    event_type: Literal[EventType.BET] = EventType.BET
    player_id: str
    team_id: Optional[str] = None
    bet_amount: float
    bankroll_after: float
    true_count: float
    cards_remaining: int
    is_shuffle: bool = False


class OutcomeEvent(Event):
    event_type: Literal[EventType.OUTCOME] = EventType.OUTCOME
    player_id: str
    result: str
    payout: float
    player_hand_value: Optional[int] = None
    dealer_upcard_value: Optional[int] = None
    bankroll_after: float


class ActionEvent(Event):
    event_type: Literal[EventType.ACTION] = EventType.ACTION
    player_id: str
    action: str
    player_hand_value: int
    dealer_upcard_value: int
    true_count: float


class SeatEvent(Event):
    event_type: Literal[EventType.SEAT] = EventType.SEAT
    player_id: str
    team_id: Optional[str] = None
    true_count: float
    cards_remaining: int


class UnseatEvent(Event):
    event_type: Literal[EventType.UNSEAT] = EventType.UNSEAT
    player_id: str
    team_id: Optional[str] = None
    true_count: float
    cards_remaining: int

class CardDealtEvent(Event):
    event_type: Literal[EventType.CARD_DEALT] = EventType.CARD_DEALT
    recipient_type: str  # "PLAYER" or "DEALER"
    recipient_id: str
    hand_index: int = 0  # 0 for main/dealer, 1+ for splits

    # Card Data
    card_rank: str
    card_suit: str

    # State Snapshot (Helps the UI and Analytics)
    hand_value_after: int  # The total value of the hand after this card
    is_hidden: bool = False  # True only for the Dealer's hole card

    # Environmental Data
    true_count: float
    cards_remaining: int


class RoundStartEvent(Event):
    event_type: Literal[EventType.ROUND_START] = EventType.ROUND_START
    round_number: int
    active_player_ids: list[str]


class RoundEndEvent(Event):
    event_type: Literal[EventType.ROUND_END] = EventType.ROUND_END
    round_number: int
