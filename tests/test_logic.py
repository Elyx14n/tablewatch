"""Tests for HiLoCount, Strategy, Player, and Dealer logic."""
import pytest
from game.card import Card, Rank, Suit
from game.hand import Hand
from game.house import HouseRules
from game.strategy import Strategy
from game.player import Player
from game.dealer import Dealer
from game.count import HiLoCount
from game.shoe import Shoe
from conftest import make_card


# ---------------------------------------------------------------------------
# HiLoCount
# ---------------------------------------------------------------------------

class TestHiLoCount:
    def test_starts_at_zero(self):
        count = HiLoCount()
        assert count.running_count == 0
        assert count.cards_seen == 0

    def test_low_cards_increment_count(self):
        count = HiLoCount()
        for rank in [Rank.TWO, Rank.THREE, Rank.FOUR, Rank.FIVE, Rank.SIX]:
            count.update(make_card(rank))
        assert count.running_count == 5

    def test_high_cards_decrement_count(self):
        count = HiLoCount()
        for rank in [Rank.TEN, Rank.JACK, Rank.QUEEN, Rank.KING, Rank.ACE]:
            count.update(make_card(rank))
        assert count.running_count == -5

    def test_neutral_cards_dont_change_count(self):
        count = HiLoCount()
        for rank in [Rank.SEVEN, Rank.EIGHT, Rank.NINE]:
            count.update(make_card(rank))
        assert count.running_count == 0

    def test_cards_seen_increments(self):
        count = HiLoCount()
        count.update(make_card(Rank.TWO))
        count.update(make_card(Rank.TEN))
        assert count.cards_seen == 2

    def test_true_count_divides_by_decks(self):
        count = HiLoCount()
        count.running_count = 6
        true_count = count.get_true_count(decks_remaining=2.0)
        assert true_count == 3.0

    def test_true_count_zero_decks_returns_zero(self):
        count = HiLoCount()
        count.running_count = 6
        assert count.get_true_count(decks_remaining=0.0) == 0.0

    def test_reset_clears_count(self):
        count = HiLoCount()
        count.update(make_card(Rank.TWO))
        count.update(make_card(Rank.THREE))
        count.reset()
        assert count.running_count == 0
        assert count.cards_seen == 0

    def test_balanced_deck_sums_to_zero(self):
        """A full standard deck should have a running count of 0."""
        count = HiLoCount()
        shoe = Shoe(num_decks=1)
        for card in shoe.draw_pile:
            count.update(card)
        assert count.running_count == 0


# ---------------------------------------------------------------------------
# Strategy
# ---------------------------------------------------------------------------

class TestStrategyBetting:
    def test_no_counting_bets_table_min(self, rules):
        strategy = Strategy(rules=rules, skill=1.0, counting=0.0)
        bet = strategy.calculate_bet(
            table_min=25, table_max=5000, bankroll=1000, true_count=5.0
        )
        assert bet == 25.0

    def test_bet_capped_at_bankroll(self, rules):
        strategy = Strategy(rules=rules, skill=1.0, counting=0.0)
        bet = strategy.calculate_bet(
            table_min=25, table_max=5000, bankroll=10, true_count=0.0
        )
        assert bet <= 10.0

    def test_counter_bets_more_at_high_count(self, rules):
        strategy = Strategy(rules=rules, skill=1.0, counting=1.0)
        low_bet = strategy.calculate_bet(
            table_min=25, table_max=5000, bankroll=10000, true_count=-2.0
        )
        high_bet = strategy.calculate_bet(
            table_min=25, table_max=5000, bankroll=10000, true_count=5.0
        )
        assert high_bet > low_bet


class TestStrategyActions:
    def _hand(self, *ranks) -> Hand:
        return Hand(cards=[make_card(r) for r in ranks], bet=25)

    def test_returns_valid_action(self, rules):
        strategy = Strategy(rules=rules, skill=1.0, counting=0.0)
        hand = self._hand(Rank.SEVEN, Rank.EIGHT)
        dealer_up = make_card(Rank.SIX)
        action = strategy.get_action(hand=hand, dealer_upcard=dealer_up)
        assert action in ("H", "S", "D", "SP", "SR")

    def test_stand_on_hard_20(self, rules):
        strategy = Strategy(rules=rules, skill=1.0, counting=0.0)
        hand = self._hand(Rank.KING, Rank.QUEEN)
        action = strategy.get_action(
            hand=hand, dealer_upcard=make_card(Rank.TEN), can_double=False
        )
        assert action == "S"

    def test_hit_on_hard_8(self, rules):
        strategy = Strategy(rules=rules, skill=1.0, counting=0.0)
        hand = self._hand(Rank.THREE, Rank.FIVE)
        action = strategy.get_action(
            hand=hand, dealer_upcard=make_card(Rank.SEVEN), can_double=False
        )
        assert action == "H"

    def test_split_aces(self, rules):
        strategy = Strategy(rules=rules, skill=1.0, counting=0.0)
        hand = self._hand(Rank.ACE, Rank.ACE)
        action = strategy.get_action(
            hand=hand, dealer_upcard=make_card(Rank.SEVEN), can_split=True
        )
        assert action == "SP"

    def test_no_split_when_cant_split(self, rules):
        strategy = Strategy(rules=rules, skill=1.0, counting=0.0)
        hand = self._hand(Rank.EIGHT, Rank.EIGHT)
        # When can_split=False, should not return SP
        action = strategy.get_action(
            hand=hand, dealer_upcard=make_card(Rank.TEN), can_split=False
        )
        assert action != "SP"

    def test_surrender_hard_16_vs_ten(self, rules):
        strategy = Strategy(rules=rules, skill=1.0, counting=0.0)
        hand = self._hand(Rank.TEN, Rank.SIX)
        action = strategy.get_action(
            hand=hand,
            dealer_upcard=make_card(Rank.TEN),
            can_double=False,
            can_surrender=True,
        )
        assert action == "SR"


# ---------------------------------------------------------------------------
# Player
# ---------------------------------------------------------------------------

class TestPlayer:
    def test_initial_state(self, player):
        assert player.bankroll == 1000.0
        assert player.total_hands == 0
        assert player.net_profit == 0.0

    def test_place_bet_reduces_bankroll(self, player):
        player.place_bet(100)
        assert player.bankroll == 900.0
        assert player.total_wagered == 100.0

    def test_place_bet_exceeds_bankroll_raises(self, player):
        with pytest.raises(ValueError):
            player.place_bet(9999)

    def test_receive_payout_increases_bankroll(self, player):
        player.place_bet(100)
        player.receive_payout(200)
        assert player.bankroll == 1100.0

    def test_record_win_loss_push(self, player):
        player.record_win()
        player.record_win()
        player.record_loss()
        player.record_push()
        assert player.hands_won == 2
        assert player.hands_lost == 1
        assert player.hands_pushed == 1
        assert player.total_hands == 4

    def test_win_rate(self, player):
        player.record_win()
        player.record_loss()
        assert player.win_rate == 0.5

    def test_add_and_clear_hands(self, player):
        hand = Hand(cards=[], bet=25)
        player.add_hand(hand)
        assert player.has_hands
        player.clear_hands()
        assert not player.has_hands

    def test_net_profit_after_loss(self, player):
        player.place_bet(100)
        # No payout — bankroll is now 900, profit is -100
        assert player.net_profit == -100.0


# ---------------------------------------------------------------------------
# Dealer
# ---------------------------------------------------------------------------

class TestDealer:
    def _dealer_with_hand(self, rules, shoe, *ranks) -> Dealer:
        d = Dealer(shoe=shoe, rules=rules)
        hand = Hand(cards=[make_card(r) for r in ranks], bet=0)
        d.set_hand(hand)
        return d

    def test_should_hit_below_17(self, rules, shoe):
        d = self._dealer_with_hand(rules, shoe, Rank.SEVEN, Rank.NINE)  # 16
        assert d.should_hit

    def test_should_stand_at_17(self, rules, shoe):
        d = self._dealer_with_hand(rules, shoe, Rank.TEN, Rank.SEVEN)  # 17
        assert not d.should_hit

    def test_should_stand_above_17(self, rules, shoe):
        d = self._dealer_with_hand(rules, shoe, Rank.TEN, Rank.NINE)  # 19
        assert not d.should_hit

    def test_offers_insurance_on_ace(self, rules, shoe):
        d = self._dealer_with_hand(rules, shoe, Rank.ACE, Rank.FIVE)
        assert d.offers_insurance()

    def test_no_insurance_on_non_ace(self, rules, shoe):
        d = self._dealer_with_hand(rules, shoe, Rank.TEN, Rank.SEVEN)
        assert not d.offers_insurance()

    def test_has_blackjack(self, rules, shoe):
        d = self._dealer_with_hand(rules, shoe, Rank.ACE, Rank.KING)
        assert d.has_blackjack()

    def test_upcard_set_on_set_hand(self, rules, shoe):
        d = self._dealer_with_hand(rules, shoe, Rank.NINE, Rank.SEVEN)
        assert d.upcard is not None

    def test_clear_hand(self, rules, shoe):
        d = self._dealer_with_hand(rules, shoe, Rank.TEN, Rank.SEVEN)
        d.clear_hand()
        assert d.hand is None
        assert d.upcard is None
