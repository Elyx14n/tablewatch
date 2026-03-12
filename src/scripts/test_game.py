import signal
from typing import List
from blackjack.game import BlackjackGame
from blackjack.house import HouseRules
from blackjack.strategy import Strategy, PlayerRole, ROLE_CONFIGS
from blackjack.player import Player
from blackjack.events import Event, SeatEvent, UnseatEvent, BetEvent


def make_team_player(
    player_id: str,
    role: PlayerRole,
    team_id: str | None,
    bankroll: float,
    rules: HouseRules,
) -> Player:
    config = ROLE_CONFIGS[role]

    if role == PlayerRole.BIG_PLAYER:
        max_loss_pct = 1.0
        max_win_pct = 2.0
    else:
        max_loss_pct = 0.5
        max_win_pct = 1.0

    return Player(
        player_id=player_id,
        bankroll=float(bankroll),
        initial_bankroll=float(bankroll),
        role=role,
        team_id=team_id,
        max_session_loss_pct=max_loss_pct,
        max_session_win_pct=max_win_pct,
        strategy=Strategy(
            rules=rules,
            skill=float(
                config.get("skill") if config.get("skill") is not None else 1.0
            ),
            counting=float(
                config.get("counting") if config.get("counting") is not None else 0.0
            ),
            bet_spread=config.get("bet_spread"),
            kelly_unit=float(
                config.get("kelly_unit")
                if config.get("kelly_unit") is not None
                else 0.0
            ),
        ),
    )


def run_scenario(scenario_name: str, active_players, bench_players):
    print(f"\n{'='*70}")
    print(f"  {scenario_name}")
    print(f"{'='*70}")

    rules = HouseRules()
    game = BlackjackGame(
        table_id=f"table_{scenario_name.lower().replace(' ', '_')}",
        players=active_players,
        bench=bench_players,
        rules=rules,
        num_decks=6,
        penetration=0.6,
        table_min=25.0,
        table_max=5000.0,
        delay_seconds=0.1,
    )

    def handle_shutdown(signum, frame):
        print("\nGraceful shutdown requested. Finishing current round...")
        game.shutdown()

    signal.signal(signal.SIGINT, handle_shutdown)

    events: List[Event] = game.run()

    all_players = active_players + bench_players
    total_pl = 0
    for player in all_players:
        profit = player.net_profit
        total_pl += profit
        sign = "+" if profit > 0 else "" if profit == 0 else "-"
        role_display = f"[{player.role.value}]"
        team_display = f" (team: {player.team_id})" if player.team_id else ""
        print(
            f"  {player.player_id:<20} {role_display:<18} {team_display:<15}"
            f"  hands: {player.total_hands:<4}"
            f"  P&L: {sign}${abs(profit):>7.0f}"
        )

    seat_events: list[SeatEvent] = [e for e in events if isinstance(e, SeatEvent)]
    unseat_events: list[UnseatEvent] = [e for e in events if isinstance(e, UnseatEvent)]

    if seat_events or unseat_events:
        print(f"\n  Wonging Activity:")
        print(f"    Mid-shoe entries:  {len(seat_events)}")
        print(f"    Mid-shoe exits:    {len(unseat_events)}")

        wongers = {e.player_id for e in seat_events}
        for player_id in wongers:
            player_seat_count = len(
                [e for e in seat_events if e.player_id == player_id]
            )
            print(f"      {player_id}: {player_seat_count} entries")

        if seat_events:
            avg_entry_tc = sum(e.true_count for e in seat_events if e.true_count) / len(
                seat_events
            )
            print(f"    Avg entry TC:      {avg_entry_tc:.2f}")

    teams = {p.team_id for p in all_players if p.team_id}
    if teams:
        print(f"\n  Team Analysis:")
        print(
            f"    Team P&L: {"+" if total_pl > 0 else "" if total_pl == 0 else "-"}${abs(total_pl):,.0f}"
        )
        for team_id in teams:
            team_events: list[BetEvent] = [e for e in events if isinstance(e, BetEvent)]
            if team_events:
                total_wagered = sum(e.bet_amount for e in team_events if e.bet_amount)
                print(f"    {team_id}: ${total_wagered:,.0f} total wagered")


def main():
    rules = HouseRules()
    run_scenario(
        "Scenario 6: Full-Scale Professional Team",
        active_players=[
            make_team_player(
                "spotter_alice", PlayerRole.SPOTTER, "team_omega", 15000, rules
            ),
            make_team_player(
                "spotter_bob", PlayerRole.SPOTTER, "team_omega", 15000, rules
            ),
        ],
        bench_players=[
            make_team_player(
                "bp_carlos", PlayerRole.BIG_PLAYER, "team_omega", 300000, rules
            ),
            make_team_player(
                "counter_diana", PlayerRole.BACK_COUNTER, "team_omega", 50000, rules
            ),
        ],
    )
    print(f"\n{'='*70}")


if __name__ == "__main__":
    main()
