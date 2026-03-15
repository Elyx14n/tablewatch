from enum import Enum
from pydantic import BaseModel, ConfigDict


class Rank(Enum):
    ACE = 1
    TWO = 2
    THREE = 3
    FOUR = 4
    FIVE = 5
    SIX = 6
    SEVEN = 7
    EIGHT = 8
    NINE = 9
    TEN = 10
    JACK = 11
    QUEEN = 12
    KING = 13


class Suit(str, Enum):
    CLUBS = "c"
    DIAMONDS = "d"
    HEARTS = "h"
    SPADES = "s"


class Card(BaseModel):
    rank: Rank
    suit: Suit
    model_config = ConfigDict(frozen=True)

    @property
    def value(self) -> int:
        return min(self.rank.value, 10)
