from typing import Optional

from .shoe import Shoe
from .hand import Hand
from .house import HouseRules


class Dealer:
    def __init__(self, shoe: Shoe, rules: HouseRules):
        self.shoe = shoe
        self.rules = rules
        self.hand: Optional[Hand] = None

    def set_hand(self, hand: Hand) -> None:
        self.hand = hand

    def clear_hand(self) -> None:
        self.hand = None

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