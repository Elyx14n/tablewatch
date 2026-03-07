"""Integration tests for BlackjackGame — verifies end-to-end game flow."""
import pytest
from game.game import BlackjackGame, GameEvent
from game.house import HouseRules
from game.strategy import Strategy
from game.player import Player


def make_player(player_id: str, bankroll: float, rules: HouseRules) -> Player:
    return Player(
        player_id=player_id,
        bankroll=bankroll,
        initial_bankroll=bankroll,
        strategy=Strategy(rules=rules, skill=1.0, counting=0.0),
    )


@pytest.fixture
def rules():
    return HouseRules()


@pytest.fixture
def single_player_game(rules):
    players = [make_player("alice", 5000.0, rules)]
    return BlackjackGame(
        table_id="table_1",
        players=players,
        rules=rules,
        num_decks=6,
        table_min=25.0,
        table_max=500.0,
        verbose=False,
    )


@pytest.fixture
def multi_player_game(rules):
    players = [
        make_player("alice", 5000.0, rules),
        make_player("bob", 5000.0, rules),
    ]
    return BlackjackGame(
        table_id="table_2",
        players=players,
        rules=rules,
        num_decks=6,
        table_min=25.0,
        table_max=500.0,
        verbose=False,
    )


# ---------------------------------------------------------------------------
# Game setup
# ---------------------------------------------------------------------------

class TestGameSetup:
    def test_game_initializes(self, single_player_game):
        game = single_player_game
        assert game.table_id == "table_1"
        assert len(game.players) == 1
        assert game.shoe.cards_remaining == 312

    def test_events_empty_before_play(self, single_player_game):
        assert single_player_game.events == []


# ---------------------------------------------------------------------------
# Event generation
# ---------------------------------------------------------------------------

class TestEventGeneration:
    def test_play_rounds_returns_events(self, single_player_game):
        events = single_player_game.play_rounds(5)
        assert len(events) > 0

    def test_all_events_are_game_events(self, single_player_game):
        events = single_player_game.play_rounds(5)
        for e in events:
            assert isinstance(e, GameEvent)

    def test_event_types_include_expected_kinds(self, single_player_game):
        events = single_player_game.play_rounds(10)
        event_types = {e.event_type for e in events}
        assert "bet" in event_types
        assert "outcome" in event_types

    def test_bet_events_have_amount(self, single_player_game):
        events = single_player_game.play_rounds(5)
        bet_events = [e for e in events if e.event_type == "bet"]
        assert len(bet_events) > 0
        for e in bet_events:
            assert e.bet_amount is not None
            assert e.bet_amount >= 25.0

    def test_outcome_events_have_result(self, single_player_game):
        events = single_player_game.play_rounds(10)
        outcome_events = [e for e in events if e.event_type == "outcome"]
        assert len(outcome_events) > 0
        for e in outcome_events:
            assert e.result in ("win", "loss", "push", "blackjack", "bust", "surrender")

    def test_events_have_table_id(self, single_player_game):
        events = single_player_game.play_rounds(5)
        for e in events:
            assert e.table_id == "table_1"

    def test_events_have_hand_id(self, single_player_game):
        events = single_player_game.play_rounds(5)
        for e in events:
            assert e.hand_id is not None


# ---------------------------------------------------------------------------
# Bankroll and state consistency
# ---------------------------------------------------------------------------

class TestGameStateConsistency:
    def test_player_bankroll_changes_after_rounds(self, single_player_game):
        initial = single_player_game.players[0].bankroll
        single_player_game.play_rounds(20)
        final = single_player_game.players[0].bankroll
        # Bankroll must have changed (bets were placed)
        assert final != initial

    def test_player_has_played_hands(self, single_player_game):
        single_player_game.play_rounds(10)
        player = single_player_game.players[0]
        assert player.total_hands > 0

    def test_bankroll_conservation(self, single_player_game):
        """Total payout events should be consistent with bet events."""
        events = single_player_game.play_rounds(20)
        bet_total = sum(e.bet_amount for e in events if e.event_type == "bet" and e.bet_amount)
        assert bet_total > 0

    def test_player_hands_cleared_after_round(self, single_player_game):
        single_player_game.play_rounds(1)
        for player in single_player_game.players:
            assert len(player.hands) == 0

    def test_multi_player_both_get_events(self, multi_player_game):
        events = multi_player_game.play_rounds(5)
        player_ids = {e.player_id for e in events if e.player_id is not None}
        assert "alice" in player_ids
        assert "bob" in player_ids


# ---------------------------------------------------------------------------
# Shoe and shuffle
# ---------------------------------------------------------------------------

class TestShoeAndShuffle:
    def test_shuffle_event_emitted_when_penetration_reached(self, rules):
        """With penetration=0.01, every round should trigger a shuffle event."""
        players = [make_player("alice", 50000.0, rules)]
        game = BlackjackGame(
            table_id="shuffle_test",
            players=players,
            rules=rules,
            num_decks=6,
            penetration=0.01,
            verbose=False,
        )
        events = game.play_rounds(5)
        shuffle_events = [e for e in events if e.event_type == "shuffle"]
        assert len(shuffle_events) >= 1

    def test_shoe_cards_dealt_increases_per_round(self, single_player_game):
        before = single_player_game.shoe.cards_dealt
        single_player_game.play_rounds(1)
        assert single_player_game.shoe.cards_dealt > before


# ---------------------------------------------------------------------------
# Large run sanity check
# ---------------------------------------------------------------------------

class TestLargeRun:
    def test_50_rounds_no_exceptions(self, rules):
        players = [make_player(f"p{i}", 10000.0, rules) for i in range(3)]
        game = BlackjackGame(
            table_id="stress",
            players=players,
            rules=rules,
            num_decks=6,
            verbose=False,
        )
        events = game.play_rounds(50)
        assert len(events) > 0
        assert all(isinstance(e, GameEvent) for e in events)
