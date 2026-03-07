from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from datetime import datetime, timezone
import logging

from .player import Player
from .dealer import Dealer
from .shoe import Shoe
from .card import Card
from .hand import Hand
from .house import HouseRules
from .count import HiLoCount

logger = logging.getLogger(__name__)


class GameEvent(BaseModel):
    event_id: str
    timestamp: datetime
    table_id: str
    hand_id: str
    event_type: str  # 'bet', 'action', 'outcome', 'shuffle'

    # Player context
    player_id: Optional[str] = None

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
        penetration: float = 0.75,
        table_min: float = 25.0,
        table_max: float = 5000.0,
        verbose: bool = True,
    ):
        self.table_id = table_id
        self.players = players
        self.rules = rules
        self.table_min = table_min
        self.table_max = table_max
        self.shoe = Shoe(num_decks=num_decks, penetration=penetration)
        self.dealer = Dealer(shoe=self.shoe, rules=rules)
        self.count = HiLoCount()
        self.events: List[GameEvent] = []
        self.hand_counter = 0
        if not verbose:
            logging.getLogger(__name__).disabled = True

    def play_rounds(self, num_rounds: int) -> List[GameEvent]:
        logger.info(f"Starting {num_rounds} rounds on table {self.table_id}")

        for round_num in range(num_rounds):
            if self.shoe.needs_shuffle:
                self._shuffle()

            self._play_round(round_num)
            self.players = [p for p in self.players if p.bankroll >= self.table_min]

            if not self.players:
                logger.info("No players remaining, ending game")
                break

        logger.info(
            f"Completed {round_num + 1} rounds, generated {len(self.events)} events"
        )
        return self.events

    def _play_round(self, round_num: int):
        self.hand_counter += 1
        hand_id = f"{self.table_id}_H{self.hand_counter}"

        # 1. Collect bets
        for player in self.players:
            bet = player.strategy.calculate_bet(
                table_min=self.table_min,
                table_max=self.table_max,
                bankroll=player.bankroll,
                true_count=self.count.get_true_count(self.shoe.decks_remaining),
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
                    bet_amount=bet,
                    true_count=self.count.get_true_count(self.shoe.decks_remaining),
                    cards_remaining=self.shoe.cards_remaining,
                )
            )

        # 2. Deal initial cards
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

        # 3. Check for dealer blackjack
        if dealer_hand.is_blackjack:
            self.count.update(dealer_hole)  # Count HiLo
            self._resolve_dealer_blackjack(hand_id)
            self._cleanup_round()
            return

        # 4. Play each player's hands
        for player in self.players:
            self._play_player_hands(player, dealer_upcard, hand_id)

        # 5. Dealer plays (only if at least one non-busted, non-blackjack hand needs resolution)
        active_hands = sum(
            1 for p in self.players
            for h in p.hands
            if not h.is_busted and not h.is_blackjack
        )
        if active_hands > 0:
            self.count.update(dealer_hole)
            self._play_dealer_hand()

        # 6. Resolve remaining hands
        self._resolve_hands(hand_id)

        # 7. Cleanup
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
                if hand.is_split and hand.cards[0].rank.value == 1 and len(hand.cards) == 2:
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
                    and (self.rules.resplit_aces or not hand.is_split or hand.cards[0].rank.value != 1)
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
                        action=action,
                        player_hand_value=hand.value,
                        dealer_upcard_value=dealer_upcard.value,
                        true_count=self.count.get_true_count(self.shoe.decks_remaining),
                    )
                )

                if action == "H":
                    card = self.shoe.draw()
                    self.count.update(card)
                    hand.add_card(card)

                elif action == "S":
                    break

                elif action == "D":
                    player.place_bet(hand.bet)  # charge original bet before doubling
                    hand.double_down()
                    card = self.shoe.draw()
                    self.count.update(card)
                    hand.add_card(card)
                    break

                elif action == "SP":
                    split_card = hand.split()
                    new_hand = Hand(cards=[split_card], bet=hand.bet, is_split=True)
                    player.place_bet(hand.bet)
                    player.add_hand(new_hand)
                    # Deal one card to each split hand
                    c1 = self.shoe.draw()
                    self.count.update(c1)
                    hand.add_card(c1)
                    c2 = self.shoe.draw()
                    self.count.update(c2)
                    new_hand.add_card(c2)
                    # Queue new hand for play in this round
                    hands_to_play.append(new_hand)
                    # Split aces: no further action on current hand either
                    if hand.cards[0].rank.value == 1:
                        break

                elif action == "SR":
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
        logger.info(f"Shuffling shoe on table {self.table_id}")
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

    def _emit_event(self, event: GameEvent):
        """Add event to buffer (or send to Kafka in production)"""
        self.events.append(event)
