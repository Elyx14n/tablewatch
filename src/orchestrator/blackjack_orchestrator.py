import redis
import psycopg2
import random
import multiprocessing
from pydantic import BaseModel, ConfigDict
from pathlib import Path
from abc import ABC
from concurrent.futures import ProcessPoolExecutor
from typing import List, Tuple
from blackjack.game import BlackjackGame
from blackjack.player import Player
from blackjack.house import HouseRules
from blackjack.strategy import Strategy, PlayerRole


class Orchestrator(BaseModel, ABC):
    db_host: str = "localhost"
    db_port: int = 6379
    db_name: str = "tablewatch"
    db_user: str = "tablewatch"
    db_password: str = "tablewatch"
    redis_host: str = "localhost"
    redis_port: int = 6379
    queries_dir: Path = Path(__file__).parent.parent / "db" / "queries"
    model_config = ConfigDict(frozen=False)

    def __post_init_post_parse__(self):
        self.conn = psycopg2.connect(
            host=self.db_host,
            port=self.db_port,
            dbname=self.db_name,
            user=self.db_user,
            password=self.db_password,
        )
        self.redis = redis.Redis(
            host=self.redis_host, port=self.redis_port, decode_responses=True
        )


class GameSpawner(Orchestrator):
    def __init__(
        self,
        delay_seconds: float = 0.5,
    ):
        self.delay = delay_seconds
        self.tables: List[Tuple] = []
        self.players: List[Tuple] = []

    def load_fixtures(self):
        cur = self.conn.cursor()
        query = (self.queries_dir / "load_tables_for_active_players.sql").read_text()
        cur.execute(query)
        self.tables = cur.fetchall()
        print(f"Loaded {len(self.tables)} tables")

        query = (self.queries_dir / "load_active_players.sql").read_text()
        cur.execute(query)
        self.players = cur.fetchall()
        print(f"Loaded {len(self.players)} active players")

    def spawn_player(self, player_row: Tuple) -> Player:
        (
            player_id,
            role,
            team_id,
            bankroll,
            initial_bankroll,
            skill,
            counting,
            kelly_unit,
            bet_spread,
            max_session_loss_pct,
            max_session_win_pct,
        ) = player_row

        rules = HouseRules()
        return Player(
            player_id=player_id,
            bankroll=float(bankroll),
            initial_bankroll=float(initial_bankroll),
            role=PlayerRole(role),
            team_id=team_id,
            max_session_loss_pct=float(max_session_loss_pct),
            max_session_win_pct=float(max_session_win_pct),
            strategy=Strategy(
                rules=rules,
                skill=float(skill),
                counting=float(counting),
                bet_spread=bet_spread,
                kelly_unit=float(kelly_unit),
            ),
        )

    def run_game(self, table_row: Tuple):
        table_id, table_min, table_max, num_decks, penetration = table_row
        num_players = random.randint(3, 7)
        if len(self.players) < num_players:
            print(f"Warning: Not enough active players for {table_id}")
            return

        assigned_player_rows = random.sample(self.players, num_players)

        active_players = []
        bench_players = []

        for player_row in assigned_player_rows:
            player = self.spawn_player(player_row)
            role = player.role

            if role in [PlayerRole.SPOTTER, PlayerRole.CASUAL]:
                active_players.append(player)
            elif role in [PlayerRole.BIG_PLAYER, PlayerRole.BACK_COUNTER]:
                bench_players.append(player)
            else:
                active_players.append(player)

        rules = HouseRules()
        game = BlackjackGame(
            table_id=table_id,
            players=active_players,
            bench=bench_players,
            rules=rules,
            num_decks=num_decks,
            penetration=float(penetration),
            table_min=float(table_min),
            table_max=float(table_max),
            delay_seconds=self.delay,
            redis_host=self.redis_host,
            redis_port=self.redis_port,
        )
        game.run()

    def spawn_games(self, max_workers: int = 100):
        print(f"Spawning {len(self.tables)} games with {max_workers}...")
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            executor.map(self.run_game, self.tables)
        print("All games completed")


if __name__ == "__main__":
    multiprocessing.set_start_method("spawn", force=True)  # Required for Windows
    spawner = GameSpawner(delay_seconds=0.5)
    spawner.load_fixtures()
    spawner.spawn_games(max_workers=10)

# import time
# from .blackjack_orchestrator import Orchestrator


# class StrategyOrchestrator(Orchestrator):
#     def __init__(
#         self,
#         check_interval_seconds: int = 30,
#     ):
#         self.check_interval = check_interval_seconds

#     def run(self):
#         print(f"Strategy Orchestrator started (check interval: {self.check_interval}s)")
#         while True:
#             try:
#                 self.detect_and_backoff_counters()
#                 self.adjust_team_configs()
#                 self.clear_expired_cooldowns()
#             except Exception as e:
#                 print(f"Error in orchestrator loop: {e}")

#             time.sleep(self.check_interval)

#     def detect_and_backoff_counters(self):
#         cur = self.conn.cursor()
#         query = (self.queries_dir / "detect_high_bet_spreads.sql").read_text()
#         cur.execute(query)

#         suspected_counters = cur.fetchall()

#         for player_id, bet_spread in suspected_counters:
#             print(
#                 f"Detected suspected counter: {player_id} (bet spread: {bet_spread:.1f}:1)"
#             )

#             cur.execute(
#                 """
#                 UPDATE players
#                 SET
#                     is_active = false,
#                     cooldown_until = NOW() + INTERVAL '24 hours',
#                     backoff_reason = 'HIGH_BET_SPREAD',
#                     updated_at = NOW()
#                 WHERE player_id = %s
#             """,
#                 (player_id,),
#             )

#             self.redis.publish("backoffs", player_id)
#             print(f"Sent backoff signal for {player_id}")

#         self.conn.commit()

#     def adjust_team_configs(self):
#         cur = self.conn.cursor()
#         query = (self.queries_dir / "team_performance_24h.sql").read_text()
#         reduce_kelly = (self.queries_dir / "lower_kelly_betting.sql").read_text()
#         increase_kelly = (self.queries_dir / "increase_kelly_betting.sql").read_text()
#         update_team_config = (self.queries_dir / "update_team_config.sql").read_text()

#         cur.execute(query)
#         teams = cur.fetchall()

#         for team_id, total_pl in teams:
#             if total_pl < -50000:
#                 print(f"Team {team_id} down ${abs(total_pl):.0f} - reducing kelly unit")
#                 cur.execute(
#                     reduce_kelly,
#                     (team_id,),
#                 )

#             elif total_pl > 100000:
#                 print(f"Team {team_id} up ${total_pl:.0f} - increasing kelly unit")
#                 cur.execute(
#                     increase_kelly,
#                     (team_id,),
#                 )

#             cur.execute(
#                 update_team_config,
#                 (team_id, total_pl),
#             )

#         self.conn.commit()

#     def clear_expired_cooldowns(self):
#         cur = self.conn.cursor()
#         query = (self.queries_dir / "reset_player_cooldown.sql").read_text()
#         cur.execute(query)

#         cleared_count = cur.rowcount
#         if cleared_count > 0:
#             print(f"Cleared {cleared_count} player cooldowns")

#         self.conn.commit()


# if __name__ == "__main__":
#     orchestrator = StrategyOrchestrator(check_interval_seconds=30)
#     orchestrator.run()
