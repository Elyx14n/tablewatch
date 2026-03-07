"""Tests for Card, Shoe, and Hand data models."""
import pytest
from game.card import Card, Rank, Suit
from game.hand import Hand
from game.shoe import Shoe
from conftest import make_card


# ---------------------------------------------------------------------------
# Card
# ---------------------------------------------------------------------------

class TestCard:
    def test_number_card_value(self):
        card = make_card(Rank.SEVEN)
        assert card.value == 7

    def test_face_card_value_is_ten(self):
        assert make_card(Rank.JACK).value == 10
        assert make_card(Rank.QUEEN).value == 10
        assert make_card(Rank.KING).value == 10

    def test_ten_card_value(self):
        assert make_card(Rank.TEN).value == 10

    def test_ace_value_is_one(self):
        # Card.value always returns min(rank, 10); ace raw value = 1
        assert make_card(Rank.ACE).value == 1

    def test_two_through_nine_values(self):
        for n in range(2, 10):
            rank = Rank(n)
            assert make_card(rank).value == n

    def test_card_is_immutable(self):
        card = make_card(Rank.FIVE)
        with pytest.raises(Exception):
            card.rank = Rank.SIX


# ---------------------------------------------------------------------------
# Shoe
# ---------------------------------------------------------------------------

class TestShoe:
    def test_shoe_has_correct_card_count(self):
        shoe = Shoe(num_decks=6)
        assert shoe.cards_remaining == 6 * 52

    def test_single_deck_shoe(self):
        shoe = Shoe(num_decks=1)
        assert shoe.cards_remaining == 52

    def test_draw_returns_card(self):
        shoe = Shoe(num_decks=6)
        card = shoe.draw()
        assert isinstance(card, Card)

    def test_draw_decrements_remaining(self):
        shoe = Shoe(num_decks=6)
        total = shoe.cards_remaining
        shoe.draw()
        assert shoe.cards_remaining == total - 1
        assert shoe.cards_dealt == 1

    def test_penetration_percentage(self):
        shoe = Shoe(num_decks=1)  # 52 cards
        assert shoe.penetration_percentage == 0.0
        for _ in range(26):
            shoe.draw()
        assert abs(shoe.penetration_percentage - 0.5) < 0.01

    def test_needs_shuffle_triggers_at_penetration(self):
        shoe = Shoe(num_decks=1, penetration=0.5)
        # Draw 26 cards (50% of 52)
        for _ in range(26):
            shoe.draw()
        assert shoe.needs_shuffle

    def test_shuffle_resets_shoe(self):
        shoe = Shoe(num_decks=1, penetration=0.5)
        for _ in range(26):
            shoe.draw()
        assert shoe.needs_shuffle
        # draw() auto-reshuffles when needs_shuffle is True
        shoe.draw()
        # After reshuffle, deck is full again minus the one just drawn
        assert shoe.cards_remaining == 51

    def test_decks_remaining_rounds_to_half(self):
        shoe = Shoe(num_decks=6)
        # No cards drawn; 312 cards = 6 decks
        assert shoe.decks_remaining == 6.0

    def test_shoe_state_snapshot(self):
        shoe = Shoe(num_decks=6, shoe_id="test-shoe")
        state = shoe.get_state()
        assert state.shoe_id == "test-shoe"
        assert state.num_decks == 6
        assert state.cards_remaining == 312


# ---------------------------------------------------------------------------
# Hand
# ---------------------------------------------------------------------------

class TestHandValue:
    def test_simple_hard_total(self):
        hand = Hand(cards=[make_card(Rank.SEVEN), make_card(Rank.EIGHT)], bet=25)
        assert hand.value == 15
        assert not hand.is_soft

    def test_hard_twenty(self):
        hand = Hand(cards=[make_card(Rank.KING), make_card(Rank.QUEEN)], bet=25)
        assert hand.value == 20

    def test_soft_hand_with_ace(self):
        hand = Hand(cards=[make_card(Rank.ACE), make_card(Rank.SIX)], bet=25)
        assert hand.value == 17
        assert hand.is_soft

    def test_ace_counts_as_one_to_avoid_bust(self):
        hand = Hand(
            cards=[make_card(Rank.ACE), make_card(Rank.FIVE), make_card(Rank.NINE)],
            bet=25,
        )
        # Ace + 5 + 9: 11+5+9=25 > 21, so ace = 1 -> 1+5+9 = 15
        assert hand.value == 15
        assert not hand.is_soft

    def test_two_aces(self):
        hand = Hand(cards=[make_card(Rank.ACE), make_card(Rank.ACE)], bet=25)
        # 11+11=22 > 21, so one ace = 1: 11+1 = 12
        assert hand.value == 12
        assert hand.is_soft

    def test_blackjack_detection(self):
        hand = Hand(cards=[make_card(Rank.ACE), make_card(Rank.KING)], bet=25)
        assert hand.value == 21
        assert hand.is_blackjack

    def test_blackjack_requires_exactly_two_cards(self):
        hand = Hand(
            cards=[make_card(Rank.ACE), make_card(Rank.FIVE), make_card(Rank.FIVE)],
            bet=25,
        )
        assert hand.value == 21
        assert not hand.is_blackjack

    def test_split_hand_not_blackjack(self):
        hand = Hand(
            cards=[make_card(Rank.ACE), make_card(Rank.KING)], bet=25, is_split=True
        )
        assert not hand.is_blackjack

    def test_bust_detection(self):
        hand = Hand(
            cards=[make_card(Rank.TEN), make_card(Rank.KING), make_card(Rank.FIVE)],
            bet=25,
        )
        assert hand.value == 25
        assert hand.is_busted

    def test_is_pair(self):
        hand = Hand(cards=[make_card(Rank.EIGHT), make_card(Rank.EIGHT, Suit.HEARTS)], bet=25)
        assert hand.is_pair

    def test_not_pair_different_ranks(self):
        hand = Hand(cards=[make_card(Rank.EIGHT), make_card(Rank.NINE)], bet=25)
        assert not hand.is_pair


class TestHandActions:
    def test_add_card(self):
        hand = Hand(cards=[make_card(Rank.FIVE)], bet=25)
        hand.add_card(make_card(Rank.SIX))
        assert len(hand.cards) == 2
        assert hand.value == 11

    def test_double_down_doubles_bet(self):
        hand = Hand(cards=[make_card(Rank.FIVE), make_card(Rank.SIX)], bet=25)
        hand.double_down()
        assert hand.bet == 50

    def test_take_insurance(self):
        hand = Hand(cards=[make_card(Rank.TEN), make_card(Rank.FIVE)], bet=100)
        hand.take_insurance()
        assert hand.insurance_bet == 50

    def test_take_insurance_twice_raises(self):
        hand = Hand(cards=[make_card(Rank.TEN), make_card(Rank.FIVE)], bet=100)
        hand.take_insurance()
        with pytest.raises(ValueError):
            hand.take_insurance()

    def test_split_extracts_second_card(self):
        hand = Hand(cards=[make_card(Rank.EIGHT), make_card(Rank.EIGHT, Suit.HEARTS)], bet=25)
        split_card = hand.split()
        assert split_card.rank == Rank.EIGHT or split_card.rank == 8  # allow enum or int
        assert len(hand.cards) == 1
        assert hand.is_split

    def test_split_non_pair_raises(self):
        hand = Hand(cards=[make_card(Rank.SEVEN), make_card(Rank.EIGHT)], bet=25)
        with pytest.raises(ValueError):
            hand.split()
