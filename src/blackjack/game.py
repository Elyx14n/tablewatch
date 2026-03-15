import uuid
import time
import os
from typing import List, Optional, Dict
import logging
from .player import Player
from .dealer import Dealer
from .shoe import Shoe
from .card import Card
from .hand import Hand
from .house import HouseRules
from .count import HiLoCount
from .strategy import PlayerRole, Action
from .events import (
    Event,
    BetEvent,
    OutcomeEvent,
    ActionEvent,
    SeatEvent,
    UnseatEvent,
    PlayerStateEvent,
    CardDealtEvent,
    Result,
    RoundStartEvent,
    RoundEndEvent,
)
from producers.blackjack_producer import BlackjackProducer

logger = logging.getLogger(__name__)


class BlackjackGame:
    def __init__(
        self,
        table_id: str,
        players: List[Player],
        rules: HouseRules,
        num_decks: int = 6,
        penetration: float = 0.65,
        table_min: float = 25.0,
        table_max: float = 5000.0,
        bench: Optional[List[Player]] = None,
        delay_seconds: float = 0.0,
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
        self.events: List[Event] = []
        self.hand_counter = 0
        self.current_round_id: str = ""
        self.shutdown_requested = False
        self.delay = delay_seconds
        self.producer = BlackjackProducer(
            bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", ""),
            schema_registry_url=os.getenv("SCHEMA_REGISTRY_URL", ""),
            topic=os.getenv("KAFKA_TOPIC", "blackjack"),
        )

    def shutdown(self) -> None:
        self.shutdown_requested = True

    def run(self) -> List[Event]:
        try:
            round_num = 1
            all_events = []
            while self.has_active_players() and not self.shutdown_requested:
                self.events.clear()
                self._add_event(
                    RoundStartEvent,
                    round_number=round_num,
                    active_player_ids=self._get_active_players_ids(),
                )
                self._play_round()
                self._add_event(
                    RoundEndEvent,
                    round_number=round_num,
                )
                all_events.extend(self.events)
                round_num += 1
            return all_events
        except Exception:
            logger.exception("Blacjack simulation run failed")
            raise
        finally:
            self.producer.close()

    def has_active_players(self) -> bool:
        return bool(self.players or self.bench)

    def _get_active_players_ids(self) -> list[str]:
        return [p.player_id for p in (self.players + self.bench)]

    def _play_round(self) -> None:
        self.current_round_id = f"round_{uuid.uuid4().hex[:12]}"
        is_shuffle = False
        if self.shoe.needs_shuffle:
            is_shuffle = True
            self._shuffle()

        self._remove_quit_players()
        self.hand_counter += 1
        hand_id = f"{self.table_id}_H{self.hand_counter}"
        true_count = self.count.get_true_count(self.shoe.decks_remaining)

        self._handle_wonging(true_count)

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
            self._add_event(
                BetEvent,
                player_id=player.player_id,
                bet_amount=bet,
                bankroll_after=player.bankroll,
                true_count=true_count,
                cards_remaining=self.shoe.cards_remaining,
                is_shuffle=is_shuffle
            )

        dealer_hand = Hand(cards=[], bet=0)

        for player in self.players:
            card = self.shoe.draw()
            self._add_card_event(card, player.hands[0], "PLAYER", player.player_id)

        dealer_upcard = self.shoe.draw()
        self._add_card_event(
            dealer_upcard, dealer_hand, "DEALER", "HOUSE", hidden=False
        )

        for player in self.players:
            card = self.shoe.draw()
            self._add_card_event(card, player.hands[0], "PLAYER", player.player_id)

        dealer_hole = self.shoe.draw()
        self._add_card_event(dealer_hole, dealer_hand, "DEALER", "HOUSE", hidden=True)

        self.dealer.set_hand(dealer_hand)

        if dealer_hand.is_blackjack:
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
            self._play_dealer_hand()

        self._resolve_hands()
        self._cleanup_round()

    def _play_player_hands(self, player: Player, dealer_upcard: Card, hand_id: str):
        hands_to_play = player.hands.copy()

        for _, hand in enumerate(hands_to_play):
            if hand.is_blackjack:
                payout = hand.bet * self.rules.blackjack_payout
                player.receive_payout(hand.bet + payout)
                player.record_win()
                self._add_event(
                    OutcomeEvent,
                    player_id=player.player_id,
                    result=Result.BJ,
                    payout=payout,
                    bankroll_after=player.bankroll,
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
                    self._add_event(
                        OutcomeEvent,
                        player_id=player.player_id,
                        result=Result.BUST,
                        payout=-hand.bet,
                        player_hand_value=hand.value,
                        bankroll_after=player.bankroll,
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

                self._add_event(
                    ActionEvent,
                    player_id=player.player_id,
                    action=action.name,
                    player_hand_value=hand.value,
                    dealer_upcard_value=dealer_upcard.value,
                    true_count=self.count.get_true_count(self.shoe.decks_remaining),
                )
                if self.delay > 0:
                    time.sleep(self.delay * 2)

                if action == Action.HIT:
                    card = self.shoe.draw()
                    hand_idx = player.hands.index(hand)
                    self._add_card_event(
                        card, hand, "PLAYER", player.player_id, h_idx=hand_idx
                    )

                elif action == Action.STAND:
                    break

                elif action == Action.DOUBLE:
                    player.place_bet(hand.bet)
                    hand.double_down()
                    card = self.shoe.draw()
                    hand_idx = player.hands.index(hand)
                    self._add_card_event(
                        card, hand, "PLAYER", player.player_id, h_idx=hand_idx
                    )
                    break

                elif action == Action.SPLIT:
                    split_card = hand.split()
                    new_hand = Hand(cards=[split_card], bet=hand.bet, is_split=True)
                    player.place_bet(hand.bet)
                    player.add_hand(new_hand)

                    # Deal cards to both split hands
                    c1 = self.shoe.draw()
                    hand_idx = player.hands.index(hand)
                    self._add_card_event(
                        c1, hand, "PLAYER", player.player_id, h_idx=hand_idx
                    )

                    c2 = self.shoe.draw()
                    new_hand_idx = player.hands.index(new_hand)
                    self._add_card_event(
                        c2, new_hand, "PLAYER", player.player_id, h_idx=new_hand_idx
                    )

                    hands_to_play.append(new_hand)
                    if hand.cards[0].rank.value == 1:
                        break

                elif action == Action.SURRENDER:
                    player.receive_payout(hand.bet * 0.5)
                    player.record_loss()
                    self._add_event(
                        OutcomeEvent,
                        player_id=player.player_id,
                        result=Result.SURRENDER,
                        payout=-hand.bet * 0.5,
                        player_hand_value=hand.value,
                        dealer_upcard_value=dealer_upcard.value,
                        bankroll_after=player.bankroll,
                    )
                    player.remove_hand(hand)
                    break

    def _play_dealer_hand(self):
        while self.dealer.should_hit:
            card = self.shoe.draw()
            assert self.dealer.hand is not None
            self._add_card_event(
                card, self.dealer.hand, "DEALER", "HOUSE", h_idx=0, hidden=False
            )

    def _resolve_dealer_blackjack(self, hand_id: str):
        for player in self.players:
            for hand_idx, hand in enumerate(player.hands):
                if hand.is_blackjack:
                    player.receive_payout(hand.bet)
                    player.record_push()
                    result = Result.PUSH
                    payout = 0.0
                else:
                    player.record_loss()
                    result = Result.LOSS
                    payout = -hand.bet

                self._add_event(
                    OutcomeEvent,
                    player_id=player.player_id,
                    result=result,
                    payout=payout,
                    bankroll_after=player.bankroll,
                )

    def _resolve_hands(self):
        assert self.dealer.hand is not None
        dealer_value = self.dealer.hand.value
        dealer_busted = self.dealer.hand.is_busted

        for player in self.players:
            for _, hand in enumerate(player.hands):
                if hand.is_busted or hand.is_blackjack:
                    continue

                if dealer_busted:
                    result = Result.WIN
                    payout = hand.bet
                    player.receive_payout(hand.bet * 2)
                    player.record_win()

                elif hand.value > dealer_value:
                    result = Result.WIN
                    payout = hand.bet
                    player.receive_payout(hand.bet * 2)
                    player.record_win()

                elif hand.value < dealer_value:
                    result = Result.LOSS
                    payout = -hand.bet
                    player.record_loss()

                else:
                    result = Result.PUSH
                    payout = 0.0
                    player.receive_payout(hand.bet)
                    player.record_push()

                self._add_event(
                    OutcomeEvent,
                    player_id=player.player_id,
                    result=result,
                    payout=payout,
                    player_hand_value=hand.value,
                    dealer_upcard_value=dealer_value,
                    bankroll_after=player.bankroll,
                )

    def _cleanup_round(self):
        for player in self.players:
            player.clear_hands()
            self._add_event(
                PlayerStateEvent,
                player_id=player.player_id,
                team_id=player.team_id,
                bankroll=player.bankroll,
                net_profit=player.net_profit,
                total_hands=player.total_hands,
                hands_won=player.hands_won,
                hands_lost=player.hands_lost,
                hands_pushed=player.hands_pushed,
                total_wagered=player.total_wagered,
                win_rate=player.win_rate,
            )
        self.dealer.clear_hand()
        if self.delay > 0:
            time.sleep(self.delay * 3)

    def _shuffle(self):
        self.shoe._reset_shoe()
        self.count.reset()
        if self.delay > 0:
            time.sleep(self.delay * 8)

    def _handle_wonging(self, true_count: float):
        entering = []
        team_signals = self._get_team_signals(true_count)
        for player in self.bench[:]:
            perceived_count = (
                team_signals.get(player.team_id, true_count)
                if player.team_id
                else true_count
            )

            if player.entry_tc is not None and perceived_count >= player.entry_tc:
                entering.append(player)
                self.bench.remove(player)
                self.players.append(player)
                self._add_event(
                    SeatEvent,
                    player_id=player.player_id,
                    team_id=player.team_id,
                    true_count=true_count,
                    cards_remaining=self.shoe.cards_remaining,
                )
                self._add_event(
                    PlayerStateEvent,
                    player_id=player.player_id,
                    team_id=player.team_id,
                    bankroll=player.bankroll,
                    net_profit=player.net_profit,
                    total_hands=player.total_hands,
                    hands_won=player.hands_won,
                    hands_lost=player.hands_lost,
                    hands_pushed=player.hands_pushed,
                    total_wagered=player.total_wagered,
                    win_rate=player.win_rate,
                )

        exiting = []
        for player in self.players[:]:
            if player.exit_tc is not None and true_count <= player.exit_tc:
                exiting.append(player)
                self.players.remove(player)
                self.bench.append(player)

                self._add_event(
                    UnseatEvent,
                    player_id=player.player_id,
                    team_id=player.team_id,
                    true_count=true_count,
                    cards_remaining=self.shoe.cards_remaining,
                )
                self._add_event(
                    PlayerStateEvent,
                    player_id=player.player_id,
                    team_id=player.team_id,
                    bankroll=player.bankroll,
                    net_profit=player.net_profit,
                    total_hands=player.total_hands,
                    hands_won=player.hands_won,
                    hands_lost=player.hands_lost,
                    hands_pushed=player.hands_pushed,
                    total_wagered=player.total_wagered,
                    win_rate=player.win_rate,
                )

    def _remove_quit_players(self):
        all_players = self.players + self.bench

        for player in all_players[:]:
            if player.should_quit_individual() or not player.can_bet:
                self._add_event(
                    PlayerStateEvent,
                    player_id=player.player_id,
                    team_id=player.team_id,
                    bankroll=player.bankroll,
                    net_profit=player.net_profit,
                    total_hands=player.total_hands,
                    hands_won=player.hands_won,
                    hands_lost=player.hands_lost,
                    hands_pushed=player.hands_pushed,
                    total_wagered=player.total_wagered,
                    win_rate=player.win_rate,
                )
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

    def _add_event(self, event_cls: type[Event], **kwargs):
        event = event_cls(
            table_id=self.table_id, round_id=self.current_round_id, **kwargs
        )
        self.events.append(event)
        self.producer.send_event(event)
        return event

    def _add_card_event(
        self,
        card: Card,
        hand: Hand,
        recipient: str,
        r_id: str,
        h_idx: int = 0,
        hidden: bool = False,
    ):
        self.count.update(card)
        hand.add_card(card)
        event = self._add_event(
            CardDealtEvent,
            recipient_type=recipient,
            recipient_id=r_id,
            hand_index=h_idx,
            card_rank=card.rank.name,
            card_suit=card.suit.name,
            hand_value_after=hand.value,
            is_hidden=hidden,
            true_count=self.count.get_true_count(self.shoe.decks_remaining),
            cards_remaining=self.shoe.cards_remaining,
        )
        self.producer.send_event(event)
        if self.delay > 0:
            time.sleep(self.delay)
