from typing import List, Optional, Dict
from pydantic import BaseModel, ConfigDict
from datetime import datetime, timezone

from .player import Player
from .dealer import Dealer
from .shoe import Shoe
from .card import Card
from .hand import Hand
from .house import HouseRules
from .count import HiLoCount
from .strategy import PlayerRole, ROLE_CONFIGS, Action


class GameEvent(BaseModel):
    event_id: str
    timestamp: datetime
    table_id: str
    hand_id: str
    event_type: str  # 'bet', 'action', 'outcome', 'shuffle', 'seat', 'unseat'

    # Player context
    player_id: Optional[str] = None
    player_role: Optional[str] = None
    team_id: Optional[str] = None

    # Game state
    true_count: Optional[float] = None
    cards_remaining: Optional[int] = None

    # Action context
    action: Optional[str] = None
    bet_amount: Optional[float] = None

    # Hand context
    player_hand_value: Optional[int] = None
    dealer_upcard_value: Optional[int] = None

    # Outcome
    result: Optional[str] = None  # 'win', 'loss', 'push', 'blackjack', 'bust'
    payout: Optional[float] = None

    model_config = ConfigDict(frozen=True)


class BlackjackGame:
    def __init__(
        self,
        table_id: str,
        players: List[Player],
        rules: HouseRules,
        num_decks: int = 6,
        penetration: float = 0.6,
        table_min: float = 25.0,
        table_max: float = 5000.0,
        bench: Optional[List[Player]] = None,
    ):
        self.table_id = table_id
        self.players = players.copy()
        self.bench = (bench or []).copy() if bench else []
        self.rules = rules
        self.table_min = table_min
        self.table_max = table_max
        self.shoe = Shoe(num_decks=num_decks, penetration=penetration)
        self.dealer = Dealer(shoe=self.shoe, rules=rules)
        self.count = HiLoCount()
        self.events: List[GameEvent] = []
        self.hand_counter = 0

    def play(self, num_rounds: int) -> List[GameEvent]:
        for _ in range(num_rounds):
            if self.shoe.needs_shuffle:
                self._shuffle()

            self._play_round()
            self._remove_quit_players()

            if not self.players and not self.bench:
                break

        return self.events

    def _play_round(self):
        self.hand_counter += 1
        hand_id = f"{self.table_id}_H{self.hand_counter}"
        true_count = self.count.get_true_count(self.shoe.decks_remaining)

        self._handle_wonging(hand_id, true_count)

        team_signals: Dict[str, float] = {}
        for player in self.players:
            if player.role == PlayerRole.SPOTTER and player.team_id:
                perceived = player.strategy._perceived_count(true_count)
                team_signals[player.team_id] = perceived

        # Collect bets
        for player in self.players:
            signal = (
                team_signals.get(player.team_id, true_count)
                if player.team_id
                else true_count
            )

            bet = player.strategy.calculate_bet(
                table_min=self.table_min,
                table_max=self.table_max,
                bankroll=player.bankroll,
                true_count=signal,
                initial_bankroll=player.initial_bankroll,
            )

            player.place_bet(bet)
            hand = Hand(cards=[], bet=bet)
            player.add_hand(hand)
            self._emit_event(
                GameEvent(
                    event_id=f"{hand_id}_{player.player_id}_bet",
                    timestamp=datetime.now(timezone.utc),
                    table_id=self.table_id,
                    hand_id=hand_id,
                    event_type="bet",
                    player_id=player.player_id,
                    player_role=player.role.value,
                    team_id=player.team_id,
                    bet_amount=bet,
                    true_count=true_count,
                    cards_remaining=self.shoe.cards_remaining,
                )
            )

        for _ in range(2):
            for player in self.players:
                card = self.shoe.draw()
                self.count.update(card)
                player.hands[0].add_card(card)

        dealer_hand = Hand(cards=[], bet=0)
        dealer_upcard = self.shoe.draw()
        self.count.update(dealer_upcard)
        dealer_hand.add_card(dealer_upcard)

        dealer_hole = self.shoe.draw()
        dealer_hand.add_card(dealer_hole)
        self.dealer.set_hand(dealer_hand)

        if dealer_hand.is_blackjack:
            self.count.update(dealer_hole)
            self._resolve_dealer_blackjack(hand_id)
            self._cleanup_round()
            return

        for player in self.players:
            self._play_player_hands(player, dealer_upcard, hand_id)

        # Dealer plays (only if at least one non-busted, non-blackjack hand needs resolution)
        active_hands = sum(
            1
            for p in self.players
            for h in p.hands
            if not h.is_busted and not h.is_blackjack
        )
        if active_hands > 0:
            self.count.update(dealer_hole)
            self._play_dealer_hand()

        self._resolve_hands(hand_id)
        self._cleanup_round()

    def _play_player_hands(self, player: Player, dealer_upcard: Card, hand_id: str):
        hands_to_play = player.hands.copy()

        for hand_idx, hand in enumerate(hands_to_play):
            if hand.is_blackjack:
                payout = hand.bet * self.rules.blackjack_payout
                player.receive_payout(hand.bet + payout)
                player.record_win()
                self._emit_event(
                    GameEvent(
                        event_id=f"{hand_id}_{player.player_id}_H{hand_idx}_blackjack",
                        timestamp=datetime.now(timezone.utc),
                        table_id=self.table_id,
                        hand_id=hand_id,
                        event_type="outcome",
                        player_id=player.player_id,
                        result="blackjack",
                        payout=payout,
                    )
                )
                continue

            while True:
                # Split aces: only one card dealt, no further action
                if (
                    hand.is_split
                    and hand.cards[0].rank.value == 1
                    and len(hand.cards) == 2
                ):
                    break

                if hand.is_busted:
                    player.record_loss()
                    self._emit_event(
                        GameEvent(
                            event_id=f"{hand_id}_{player.player_id}_H{hand_idx}_bust",
                            timestamp=datetime.now(timezone.utc),
                            table_id=self.table_id,
                            hand_id=hand_id,
                            event_type="outcome",
                            player_id=player.player_id,
                            result="bust",
                            player_hand_value=hand.value,
                        )
                    )
                    break

                can_split = (
                    hand.is_pair
                    and len(hand.cards) == 2
                    and len(player.hands) <= self.rules.max_splits
                    and player.bankroll >= hand.bet
                    and (
                        self.rules.resplit_aces
                        or not hand.is_split
                        or hand.cards[0].rank.value != 1
                    )
                )
                action = player.strategy.get_action(
                    hand=hand,
                    dealer_upcard=dealer_upcard,
                    can_double=len(hand.cards) == 2 and player.bankroll >= hand.bet,
                    can_split=can_split,
                    can_surrender=len(hand.cards) == 2 and self.rules.late_surrender,
                )

                self._emit_event(
                    GameEvent(
                        event_id=f"{hand_id}_{player.player_id}_H{hand_idx}_action",
                        timestamp=datetime.now(timezone.utc),
                        table_id=self.table_id,
                        hand_id=hand_id,
                        event_type="action",
                        player_id=player.player_id,
                        action=action.name,
                        player_hand_value=hand.value,
                        dealer_upcard_value=dealer_upcard.value,
                        true_count=self.count.get_true_count(self.shoe.decks_remaining),
                    )
                )

                if action == Action.HIT:
                    card = self.shoe.draw()
                    self.count.update(card)
                    hand.add_card(card)

                elif action == Action.STAND:
                    break

                elif action == Action.DOUBLE:
                    player.place_bet(hand.bet)
                    hand.double_down()
                    card = self.shoe.draw()
                    self.count.update(card)
                    hand.add_card(card)
                    break

                elif action == Action.SPLIT:
                    split_card = hand.split()
                    new_hand = Hand(cards=[split_card], bet=hand.bet, is_split=True)
                    player.place_bet(hand.bet)
                    player.add_hand(new_hand)
                    c1 = self.shoe.draw()
                    self.count.update(c1)
                    hand.add_card(c1)
                    c2 = self.shoe.draw()
                    self.count.update(c2)
                    new_hand.add_card(c2)
                    hands_to_play.append(new_hand)
                    if hand.cards[0].rank.value == 1:
                        break

                elif action == Action.SURRENDER:
                    player.receive_payout(hand.bet * 0.5)
                    player.record_loss()
                    self._emit_event(
                        GameEvent(
                            event_id=f"{hand_id}_{player.player_id}_H{hand_idx}_surrender",
                            timestamp=datetime.now(timezone.utc),
                            table_id=self.table_id,
                            hand_id=hand_id,
                            event_type="outcome",
                            player_id=player.player_id,
                            result="surrender",
                            payout=-hand.bet * 0.5,
                            player_hand_value=hand.value,
                            dealer_upcard_value=dealer_upcard.value,
                        )
                    )
                    player.remove_hand(hand)
                    break

    def _play_dealer_hand(self):
        while self.dealer.should_hit:
            card = self.shoe.draw()
            self.count.update(card)
            assert self.dealer.hand is not None
            self.dealer.hand.add_card(card)

    def _resolve_dealer_blackjack(self, hand_id: str):
        for player in self.players:
            for hand_idx, hand in enumerate(player.hands):
                if hand.is_blackjack:
                    player.receive_payout(hand.bet)
                    player.record_push()
                    result = "push"
                    payout = 0.0
                else:
                    player.record_loss()
                    result = "loss"
                    payout = -hand.bet

                self._emit_event(
                    GameEvent(
                        event_id=f"{hand_id}_{player.player_id}_H{hand_idx}_dealer_bj",
                        timestamp=datetime.now(timezone.utc),
                        table_id=self.table_id,
                        hand_id=hand_id,
                        event_type="outcome",
                        player_id=player.player_id,
                        result=result,
                        payout=payout,
                    )
                )

    def _resolve_hands(self, hand_id: str):
        assert self.dealer.hand is not None
        dealer_value = self.dealer.hand.value
        dealer_busted = self.dealer.hand.is_busted

        for player in self.players:
            for hand_idx, hand in enumerate(player.hands):
                if hand.is_busted or hand.is_blackjack:
                    continue

                if dealer_busted:
                    result = "win"
                    payout = hand.bet
                    player.receive_payout(hand.bet * 2)
                    player.record_win()

                elif hand.value > dealer_value:
                    result = "win"
                    payout = hand.bet
                    player.receive_payout(hand.bet * 2)
                    player.record_win()

                elif hand.value < dealer_value:
                    result = "loss"
                    payout = -hand.bet
                    player.record_loss()

                else:
                    result = "push"
                    payout = 0.0
                    player.receive_payout(hand.bet)
                    player.record_push()

                self._emit_event(
                    GameEvent(
                        event_id=f"{hand_id}_{player.player_id}_H{hand_idx}_resolve",
                        timestamp=datetime.now(timezone.utc),
                        table_id=self.table_id,
                        hand_id=hand_id,
                        event_type="outcome",
                        player_id=player.player_id,
                        result=result,
                        payout=payout,
                        player_hand_value=hand.value,
                        dealer_upcard_value=dealer_value,
                    )
                )

    def _cleanup_round(self):
        for player in self.players:
            player.clear_hands()
        self.dealer.clear_hand()

    def _shuffle(self):
        self.shoe._reset_shoe()
        self.count.reset()

        self._emit_event(
            GameEvent(
                event_id=f"{self.table_id}_shuffle_{self.hand_counter}",
                timestamp=datetime.now(timezone.utc),
                table_id=self.table_id,
                hand_id=f"shuffle_{self.hand_counter}",
                event_type="shuffle",
                cards_remaining=self.shoe.cards_remaining,
            )
        )

    def _handle_wonging(self, hand_id: str, true_count: float):
        entering = []
        team_signals = self._get_team_signals(true_count)
        for player in self.bench[:]:
            config = ROLE_CONFIGS.get(player.role, {})
            entry_tc = config.get("entry_tc")
            perceived_count = (
                team_signals.get(player.team_id, true_count)
                if player.team_id
                else true_count
            )

            if entry_tc is not None and perceived_count >= entry_tc:
                entering.append(player)
                self.bench.remove(player)
                self.players.append(player)
                self._emit_event(
                    GameEvent(
                        event_id=f"{hand_id}_{player.player_id}_seat",
                        timestamp=datetime.now(timezone.utc),
                        table_id=self.table_id,
                        hand_id=hand_id,
                        event_type="seat",
                        player_id=player.player_id,
                        player_role=player.role.value,
                        team_id=player.team_id,
                        true_count=true_count,
                        cards_remaining=self.shoe.cards_remaining,
                    )
                )

        exiting = []
        for player in self.players[:]:
            config = ROLE_CONFIGS.get(player.role, {})
            exit_tc = config.get("exit_tc")

            if exit_tc is not None and true_count <= exit_tc:
                exiting.append(player)
                self.players.remove(player)
                self.bench.append(player)

                self._emit_event(
                    GameEvent(
                        event_id=f"{hand_id}_{player.player_id}_unseat",
                        timestamp=datetime.now(timezone.utc),
                        table_id=self.table_id,
                        hand_id=hand_id,
                        event_type="unseat",
                        player_id=player.player_id,
                        player_role=player.role.value,
                        team_id=player.team_id,
                        true_count=true_count,
                        cards_remaining=self.shoe.cards_remaining,
                    )
                )

    def _remove_quit_players(self):
        all_players = self.players + self.bench

        for player in all_players[:]:
            if player.should_quit_individual():
                if player in self.players:
                    self.players.remove(player)
                if player in self.bench:
                    self.bench.remove(player)
            elif not player.can_bet:
                if player in self.players:
                    self.players.remove(player)
                if player in self.bench:
                    self.bench.remove(player)

    def _get_team_signals(self, true_count: float) -> Dict[str, float]:
        signals = {}
        for player in self.players:
            if player.role == PlayerRole.SPOTTER and player.team_id:
                perceived = player.strategy._perceived_count(true_count)
                signals[player.team_id] = perceived
        return signals

    def _emit_event(self, event: GameEvent):
        """Add event to buffer (or send to Kafka in production)"""
        self.events.append(event)
