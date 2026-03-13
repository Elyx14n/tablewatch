import psycopg2
import random
import multiprocessing
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
from typing import List, Tuple
from blackjack.game import BlackjackGame
from blackjack.player import Player
from blackjack.house import HouseRules
from blackjack.strategy import Strategy, PlayerRole
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

ROOT = Path(__file__).resolve().parent.parent

class Orchestrator(BaseSettings):
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "tablewatch"
    db_user: str = "tablewatch"
    db_password: str = "tablewatch"
    delay_seconds: float = 0.5
    queries_dir: Path = Field(default=ROOT / "db" / "queries")
    tables: List[Tuple] = Field(default_factory=list, exclude=True)
    players: List[Tuple] = Field(default_factory=list, exclude=True)

    model_config = SettingsConfigDict(
        env_file=ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def load_fixtures(self):
        print(f"Connecting to {self.db_host} to load fixtures...")
        with psycopg2.connect(
            host=self.db_host,
            port=self.db_port,
            dbname=self.db_name,
            user=self.db_user,
            password=self.db_password,
        ) as conn:
            with conn.cursor() as cur:
                table_query = (self.queries_dir / "load_tables_for_active_players.sql").read_text()
                cur.execute(table_query)
                self.tables = cur.fetchall()
                print(f"Loaded {len(self.tables)} tables")

                player_query = (self.queries_dir / "load_active_players.sql").read_text()
                cur.execute(player_query)
                self.players = cur.fetchall()
                print(f"Loaded {len(self.players)} active players")

    def spawn_player(self, player_row: Tuple) -> Player:
        (
            player_id, role, team_id, bankroll, initial_bankroll,
            skill, counting, kelly_unit, bet_spread,
            max_session_loss_pct, max_session_win_pct,
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
            if player.role in [PlayerRole.SPOTTER, PlayerRole.CASUAL]:
                active_players.append(player)
            elif player.role in [PlayerRole.BIG_PLAYER, PlayerRole.BACK_COUNTER]:
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
            delay_seconds=self.delay_seconds,
        )
        game.run()

    def spawn_games(self, max_workers: int = 10):
        print(f"Spawning {len(self.tables)} games with {max_workers} workers...")
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            executor.map(self.run_game, self.tables)
        print("All games completed")


if __name__ == "__main__":
    # Windows/macOS requirement for multiprocessing
    multiprocessing.set_start_method("spawn", force=True)
    spawner = Orchestrator(delay_seconds=0.5)
    spawner.load_fixtures()
    spawner.spawn_games(max_workers=10)
