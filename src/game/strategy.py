from typing import Literal, Dict
import random

from .hand import Hand
from .card import Card, Rank
from .house import HouseRules

SPREAD_1_TO_6 = {-2: 1, -1: 1, 0: 1, 1: 2, 2: 3, 3: 4, 4: 5, 5: 6}
SPREAD_1_TO_10 = {-2: 1, -1: 1, 0: 1, 1: 2, 2: 4, 3: 6, 4: 8, 5: 10}
SPREAD_1_TO_12 = {-2: 1, -1: 1, 0: 1, 1: 2, 2: 4, 3: 8, 4: 12, 5: 12}
SPREAD_1_TO_20 = {-2: 1, -1: 1, 0: 1, 1: 4, 2: 8, 3: 12, 4: 16, 5: 20}

Action = Literal["H", "S", "D", "SP", "SR"]

# Basic Strategy Charts
PAIR_SPLITS = {
    1: [True, True, True, True, True, True, True, True, True, True],
    10: [False, False, False, False, False, False, False, False, False, False],
    9: [False, True, True, True, True, True, False, True, True, False],
    8: [True, True, True, True, True, True, True, True, True, True],
    7: [False, True, True, True, True, True, True, False, False, False],
    6: [False, False, True, True, True, True, False, False, False, False],
    5: [False, False, False, False, False, False, False, False, False, False],
    4: [False, False, False, False, False, False, False, False, False, False],
    3: [False, False, False, True, True, True, True, False, False, False],
    2: [False, False, False, True, True, True, True, False, False, False],
}

SOFT_TOTALS = {
    10: ["S", "S", "S", "S", "S", "S", "S", "S", "S", "S"],
    9: ["S", "S", "S", "S", "S", "S", "S", "S", "S", "S"],
    8: ["S", "S", "S", "S", "S", "D", "S", "S", "S", "S"],
    7: ["H", "D", "D", "D", "D", "D", "S", "S", "H", "H"],
    6: ["H", "H", "D", "D", "D", "D", "H", "H", "H", "H"],
    5: ["H", "H", "H", "D", "D", "D", "H", "H", "H", "H"],
    4: ["H", "H", "H", "D", "D", "D", "H", "H", "H", "H"],
    3: ["H", "H", "H", "H", "D", "D", "H", "H", "H", "H"],
    2: ["H", "H", "H", "H", "D", "D", "H", "H", "H", "H"],
}

HARD_TOTALS = {
    17: ["S", "S", "S", "S", "S", "S", "S", "S", "S", "S"],
    16: ["H", "S", "S", "S", "S", "S", "H", "H", "H", "H"],
    15: ["H", "S", "S", "S", "S", "S", "H", "H", "H", "H"],
    14: ["H", "S", "S", "S", "S", "S", "H", "H", "H", "H"],
    13: ["H", "S", "S", "S", "S", "S", "H", "H", "H", "H"],
    12: ["H", "H", "H", "S", "S", "S", "H", "H", "H", "H"],
    11: ["D", "D", "D", "D", "D", "D", "D", "D", "D", "D"],
    10: ["H", "D", "D", "D", "D", "D", "D", "D", "D", "H"],
    9: ["H", "H", "D", "D", "D", "D", "H", "H", "H", "H"],
    8: ["H", "H", "H", "H", "H", "H", "H", "H", "H", "H"],
}

# Late Surrender Chart (Basic Strategy)
# Surrender hard 16 vs dealer 9, 10, A
# Surrender hard 15 vs dealer 10
SURRENDER = {
    16: [True, False, False, False, False, False, False, False, True, True],
    15: [False, False, False, False, False, False, False, False, False, True],
}


class Strategy:
    def __init__(
        self,
        rules: HouseRules,
        skill: float = 0.95,
        counting: float = 0.0,
        bet_spread: Dict[int, float] | None = None,
        kelly_unit: float = 0.0,
    ):
        self.rules = rules
        self.skill = max(0.0, min(1.0, skill))
        self.counting = max(0.0, min(1.0, counting))
        self.bet_spread = bet_spread or SPREAD_1_TO_12
        self.kelly_unit = max(0.0, min(1.0, kelly_unit))

        self._setup_strategy_charts()

    def _setup_strategy_charts(self):
        self.pair_splits = {k: v.copy() for k, v in PAIR_SPLITS.items()}
        self.soft_totals = {k: v.copy() for k, v in SOFT_TOTALS.items()}
        self.hard_totals = {k: v.copy() for k, v in HARD_TOTALS.items()}
        self.surrender = {k: v.copy() for k, v in SURRENDER.items()}

        # Adjust for DAS
        if self.rules.double_after_split:
            self.pair_splits.update(
                {
                    6: [
                        False,
                        True,
                        True,
                        True,
                        True,
                        True,
                        False,
                        False,
                        False,
                        False,
                    ],
                    4: [
                        False,
                        False,
                        False,
                        False,
                        True,
                        True,
                        False,
                        False,
                        False,
                        False,
                    ],
                    3: [False, True, True, True, True, True, True, False, False, False],
                    2: [False, True, True, True, True, True, True, False, False, False],
                }
            )

        # Adjust for no double on soft
        if not self.rules.double_on_soft_total:
            self.soft_totals.update(
                {
                    8: ["S", "S", "S", "S", "S", "S", "S", "S", "S", "S"],
                    7: ["H", "S", "S", "S", "S", "S", "S", "S", "H", "H"],
                    6: ["H", "H", "H", "H", "H", "H", "H", "H", "H", "H"],
                    5: ["H", "H", "H", "H", "H", "H", "H", "H", "H", "H"],
                    4: ["H", "H", "H", "H", "H", "H", "H", "H", "H", "H"],
                    3: ["H", "H", "H", "H", "H", "H", "H", "H", "H", "H"],
                    2: ["H", "H", "H", "H", "H", "H", "H", "H", "H", "H"],
                }
            )

    def get_action(
        self,
        hand: Hand,
        dealer_upcard: Card,
        can_double: bool = True,
        can_split: bool = False,
        can_surrender: bool = False,
    ) -> Action:
        optimal = self._get_optimal_action(
            hand, dealer_upcard, can_double, can_split, can_surrender
        )
        if random.random() < self.skill:
            return optimal
        return self._random_action(can_double, can_split, can_surrender)

    def _get_optimal_action(
        self,
        hand: Hand,
        dealer_upcard: Card,
        can_double: bool,
        can_split: bool,
        can_surrender: bool,
    ) -> Action:
        dealer_idx = self._get_dealer_index(dealer_upcard)
        if can_surrender and self.rules.late_surrender:
            if not hand.is_soft and not hand.is_pair and hand.value in self.surrender:
                if self.surrender[hand.value][dealer_idx]:
                    return "SR"
        if can_split and hand.is_pair:
            pair_val = 1 if hand.cards[0].rank.value == 1 else hand.cards[0].rank.value
            if self.pair_splits.get(pair_val, [False] * 10)[dealer_idx]:
                return "SP"
        if hand.is_soft:
            aceless = sum(c.value for c in hand.cards if c.rank != Rank.ACE)
            if aceless <= 10:
                action = self.soft_totals.get(aceless, ["H"] * 10)[dealer_idx]
                return "H" if action == "D" and not can_double else action
        if hand.value <= 8:
            return "H"
        if hand.value >= 17:
            return "S"

        action = self.hard_totals.get(hand.value, ["H"] * 10)[dealer_idx]
        return "H" if action == "D" and not can_double else action

    def _random_action(
        self, can_double: bool, can_split: bool, can_surrender: bool
    ) -> Action:
        options = ["H", "S"]
        if can_double:
            options.append("D")
        if can_split:
            options.append("SP")
        if can_surrender:
            options.append("SR")
        return random.choice(options)

    def _get_dealer_index(self, dealer_upcard: Card) -> int:
        return 0 if dealer_upcard.rank == Rank.ACE else dealer_upcard.value - 1

    def calculate_bet(
        self,
        table_min: float,
        table_max: float,
        bankroll: float,
        true_count: float = 0.0,
    ) -> float:
        if bankroll <= 0:
            return 0.0

        if self.counting < 0.1:
            return min(table_min, bankroll)

        noise = (1.0 - self.counting) * 2.0
        perceived_count = true_count + random.gauss(0, noise)

        if self.kelly_unit > 0:
            # Dynamic unit: Kelly-calibrated so that the max-spread bet at the highest
            # TC key equals kelly_unit * Kelly-optimal at that count.
            # Hi-Lo edge approximation: each TC unit above +1 adds ~0.5% player edge.
            # Variance per hand ≈ 1.3 for standard 6-deck blackjack.
            max_multiplier = max(self.bet_spread.values())
            max_tc = max(self.bet_spread.keys())
            edge_at_max = max(0.0, (max_tc - 1) * 0.005)
            dynamic_unit = (bankroll * self.kelly_unit * edge_at_max / 1.3) / max_multiplier
            unit = max(table_min, dynamic_unit)
        else:
            unit = table_min

        tc_int = int(round(perceived_count))
        if tc_int <= min(self.bet_spread.keys()):
            multiplier = self.bet_spread[min(self.bet_spread.keys())]
        elif tc_int >= max(self.bet_spread.keys()):
            multiplier = self.bet_spread[max(self.bet_spread.keys())]
        else:
            multiplier = self.bet_spread.get(tc_int, 1.0)

        bet = unit * multiplier
        return min(bet, table_max, bankroll)
