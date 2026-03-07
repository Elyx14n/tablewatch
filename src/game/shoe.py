from typing import List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, ConfigDict, Field
import random

from .card import Card, Rank, Suit


class Shoe:
    def __init__(
        self, num_decks: int = 6, penetration: float = 0.75, shoe_id: Optional[str] = None
    ):
        self.shoe_id = shoe_id or f"shoe_{id(self)}"
        self.num_decks = num_decks
        self.penetration = penetration
        self.draw_pile: List[Card] = []
        self.discard_pile: List[Card] = []
        self._build_and_shuffle()

    def _build_and_shuffle(self):
        self.draw_pile = [
            Card(rank=rank, suit=suit)
            for _ in range(self.num_decks)
            for suit in Suit
            for rank in Rank
        ]
        random.shuffle(self.draw_pile)
        self.discard_pile = []

    def _reset_shoe(self):
        self.draw_pile.extend(self.discard_pile)
        self.discard_pile = []
        random.shuffle(self.draw_pile)

    def draw(self) -> Card:
        if self.needs_shuffle:
            self._reset_shoe()

        card = self.draw_pile.pop(0)
        self.discard_pile.append(card)
        return card

    @property
    def needs_shuffle(self) -> bool:
        return self.penetration_percentage >= self.penetration

    @property
    def cards_remaining(self) -> int:
        return len(self.draw_pile)

    @property
    def cards_dealt(self) -> int:
        return len(self.discard_pile)

    @property
    def penetration_percentage(self) -> float:
        total_cards = self.num_decks * 52
        return len(self.discard_pile) / total_cards

    @property
    def decks_remaining(self) -> float:
        decks = self.cards_remaining / 52
        return round(decks * 2) / 2

    def get_state(self) -> "ShoeState":
        """Get immutable snapshot for events/logging"""
        return ShoeState(
            shoe_id=self.shoe_id,
            num_decks=self.num_decks,
            cards_remaining=self.cards_remaining,
            cards_dealt=self.cards_dealt,
            penetration=self.penetration,
        )


class ShoeState(BaseModel):
    shoe_id: str
    num_decks: int
    cards_remaining: int
    cards_dealt: int
    penetration: float
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    model_config = ConfigDict(frozen=True)
