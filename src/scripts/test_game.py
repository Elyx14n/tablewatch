from game.game import BlackjackGame
from game.house import HouseRules
from game.strategy import Strategy, SPREAD_1_TO_6
from game.player import Player


def make_player(player_id, bankroll, skill, counting, bet_spread=None, kelly_unit=0.0):
    rules = HouseRules()
    return Player(
        player_id=player_id,
        bankroll=float(bankroll),
        initial_bankroll=float(bankroll),
        strategy=Strategy(
            rules=rules,
            skill=skill,
            counting=counting,
            bet_spread=bet_spread,
            kelly_unit=kelly_unit,
        ),
    )


rules = HouseRules()

players = [
    make_player("recreational",   bankroll=30000, skill=0.70, counting=0.0),
    make_player("basic_strategy", bankroll=30000, skill=1.00, counting=0.0),
    make_player("spread_counter", bankroll=30000, skill=1.00, counting=1.0, bet_spread=SPREAD_1_TO_6),
    make_player("kelly_counter",  bankroll=30000, skill=1.00, counting=1.0, bet_spread=SPREAD_1_TO_6, kelly_unit=0.5),
]

game = BlackjackGame(
    table_id="demo_table",
    players=players,
    rules=rules,
    num_decks=6,
    penetration=0.75,
    table_min=25.0,
    table_max=500.0,
    verbose=False,
)

NUM_ROUNDS = 1000
events = game.play_rounds(NUM_ROUNDS)

# ── Summary ────────────────────────────────────────────────────────────────────
print(f"\n{'='*55}")
print(f"  TableWatch Simulation  |  {NUM_ROUNDS} rounds  |  {len(events)} events")
print(f"{'='*55}")

for player in players:
    profit = player.net_profit
    sign = "+" if profit >= 0 else ""
    print(
        f"\n  {player.player_id:<18}"
        f"  hands: {player.total_hands:<4}"
        f"  W/L/P: {player.hands_won}/{player.hands_lost}/{player.hands_pushed}"
        f"  win%: {player.win_rate:.1%}"
        f"  P&L: {sign}${profit:.0f}"
    )

# Event type breakdown
from collections import Counter
type_counts = Counter(e.event_type for e in events)
print(f"\n  Event breakdown: {dict(type_counts)}")

# Outcome breakdown
outcome_counts = Counter(
    e.result for e in events if e.event_type == "outcome" and e.result
)
print(f"  Outcomes:        {dict(outcome_counts)}")
print(f"{'='*55}\n")
