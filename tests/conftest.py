import pytest

from game.card import Card, Rank, Suit
from game.hand import Hand
from game.shoe import Shoe
from game.house import HouseRules
from game.strategy import Strategy
from game.player import Player
from game.dealer import Dealer
from game.count import HiLoCount


def make_card(rank: Rank, suit: Suit = Suit.SPADES) -> Card:
    return Card(rank=rank, suit=suit)


@pytest.fixture
def rules():
    return HouseRules()


@pytest.fixture
def perfect_strategy(rules):
    """Player who always plays basic strategy perfectly, no counting."""
    return Strategy(rules=rules, skill=1.0, counting=0.0)


@pytest.fixture
def shoe():
    return Shoe(num_decks=6)


@pytest.fixture
def player(rules):
    return Player(
        player_id="test_player",
        bankroll=1000.0,
        initial_bankroll=1000.0,
        strategy=Strategy(rules=rules, skill=1.0, counting=0.0),
    )


@pytest.fixture
def dealer_obj(shoe, rules):
    return Dealer(shoe=shoe, rules=rules)
