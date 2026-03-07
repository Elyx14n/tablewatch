from pydantic import BaseModel, ConfigDict, Field, computed_field
from typing import List

from .card import Card, Rank


class Hand(BaseModel):
    cards: List[Card] = Field(default_factory=list)
    bet: float = Field(ge=0)
    is_split: bool = False
    insurance_bet: float = 0.0
    model_config = ConfigDict(frozen=False)

    @property
    def _aces_count(self) -> int:
        return sum(1 for card in self.cards if card.rank == Rank.ACE)

    @property
    def _non_ace_total(self) -> int:
        return sum(card.value for card in self.cards if card.rank != Rank.ACE)

    @computed_field
    @property
    def value(self) -> int:
        aces = self._aces_count
        total = self._non_ace_total + (aces * 11)

        while total > 21 and aces > 0:
            total -= 10
            aces -= 1
        return total

    @computed_field
    @property
    def is_soft(self) -> bool:
        if self._aces_count == 0:
            return False
        # Soft only if at least one ace can still count as 11 without busting
        return self._non_ace_total + 11 + (self._aces_count - 1) <= 21

    @computed_field
    @property
    def is_blackjack(self) -> bool:
        return len(self.cards) == 2 and self.value == 21 and not self.is_split

    @computed_field
    @property
    def is_busted(self) -> bool:
        return self.value > 21

    @computed_field
    @property
    def is_pair(self) -> bool:
        return len(self.cards) == 2 and self.cards[0].rank == self.cards[1].rank

    def add_card(self, card: Card):
        self.cards.append(card)

    def double_down(self):
        self.bet *= 2

    def take_insurance(self):
        if self.insurance_bet > 0:
            raise ValueError("Insurance already taken")
        self.insurance_bet = self.bet / 2

    def split(self) -> Card:
        if not self.is_pair:
            raise ValueError("Cannot split non-pair")
        card = self.cards.pop()
        self.is_split = True
        return card
