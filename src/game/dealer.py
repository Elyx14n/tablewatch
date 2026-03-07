from pydantic import BaseModel
from typing import Optional

from .shoe import Shoe
from .card import Card
from .hand import Hand, Rank
from .house import HouseRules


class Dealer:
    def __init__(self, shoe: Shoe, rules: HouseRules, penetration: float = 0.75):
        self.shoe = shoe
        self.rules = rules
        self.penetration = penetration
        self.hand: Optional[Hand] = None
        self.upcard: Optional[Card] = None

    def deal_card(self) -> Card:
        return self.shoe.draw()

    def set_hand(self, hand: Hand) -> None:
        self.hand = hand
        if len(hand.cards) > 0:
            self.upcard = hand.cards[0]

    def clear_hand(self) -> None:
        self.hand = None
        self.upcard = None

    @property
    def should_hit(self) -> bool:
        if not self.hand:
            return False

        hand_value = self.hand.value
        if hand_value < self.rules.dealer_stands_on:
            return True
        if hand_value == 17 and self.rules.dealer_stands_on == 17:
            return False
        return False

    def offers_insurance(self) -> bool:
        if not self.upcard:
            return False
        return self.upcard.rank == Rank.ACE

    def has_blackjack(self) -> bool:
        if not self.hand:
            return False
        return self.hand.is_blackjack

    def needs_shuffle(self) -> bool:
        return self.shoe.needs_shuffle

    def shuffle(self) -> None:
        self.shoe._reset_shoe()


class DealerState(BaseModel):
    dealer_id: str
    hands_dealt: int = 0
    player_wins: int = 0
    dealer_busts: int = 0

    @property
    def player_win_rate(self) -> float:
        return self.player_wins / self.hands_dealt if self.hands_dealt > 0 else 0.0

    @property
    def dealer_bust_rate(self) -> float:
        return self.dealer_busts / self.hands_dealt if self.hands_dealt > 0 else 0.0
