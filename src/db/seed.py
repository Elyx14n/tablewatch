import os
import random
import json
import io
import time
import psycopg2
from blackjack.strategy import PlayerRole
from faker import Faker
from typing import List

fake = Faker()

ROLE_CONFIGS = {
    PlayerRole.CASUAL: {
        "skill_range": (0.85, 0.98),
        "counting_range": (0.0, 0.0),
        "kelly_unit_range": (0.0, 0.0),
        "bet_spread": {1: 1, 2: 1, 3: 1},
        "bankroll_range": (500, 3000),
        "max_session_loss_pct_range": (0.3, 0.7),
        "max_session_win_pct_range": (0.8, 1.5),
        "weight": 60,
    },
    PlayerRole.ADVANTAGE: {
        "skill_range": (0.98, 1.0),
        "counting_range": (0.7, 0.95),
        "kelly_unit_range": (0.005, 0.02),
        "bet_spread_options": [
            {1: 1, 2: 4, 3: 8},
            {1: 1, 2: 5, 3: 10},
        ],
        "bankroll_range": (5000, 25000),
        "max_session_loss_pct_range": (0.4, 0.6),
        "max_session_win_pct_range": (1.0, 2.0),
        "weight": 25,
    },
    PlayerRole.SPOTTER: {
        "skill_range": (0.95, 1.0),
        "counting_range": (0.85, 1.0),
        "kelly_unit_range": (0.001, 0.005),
        "bet_spread": {1: 1, 2: 1, 3: 2},
        "bankroll_range": (2000, 8000),
        "max_session_loss_pct_range": (0.5, 0.7),
        "max_session_win_pct_range": (0.5, 1.0),
        "weight": 8,
    },
    PlayerRole.BIG_PLAYER: {
        "skill_range": (0.98, 1.0),
        "counting_range": (0.0, 0.3),
        "kelly_unit_range": (0.02, 0.05),
        "bet_spread_options": [
            {1: 10, 2: 20, 3: 50},
        ],
        "bankroll_range": (30000, 100000),
        "max_session_loss_pct_range": (0.3, 0.5),
        "max_session_win_pct_range": (1.5, 3.0),
        "entry_tc_range": (0.5, 1.5),
        "exit_tc_range": (-1.5, -0.5),
        "weight": 4,
    },
    PlayerRole.BACK_COUNTER: {
        "skill_range": (0.98, 1.0),
        "counting_range": (0.9, 1.0),
        "kelly_unit_range": (0.015, 0.035),
        "bet_spread_options": [{1: 1, 2: 8, 3: 16}],
        "bankroll_range": (15000, 50000),
        "max_session_loss_pct_range": (0.4, 0.6),
        "max_session_win_pct_range": (1.2, 2.5),
        "entry_tc_range": (1.5, 2.5),
        "exit_tc_range": (-0.5, 0.5),
        "weight": 3,
    },
}


def sql_escape(value: str) -> str:
    return value.replace("\t", " ").replace("\n", " ")


def generate_player_name() -> str:
    return sql_escape(fake.unique.name())


def generate_team_name() -> str:
    return sql_escape("TEAM_" + fake.unique.word().upper())


def random_in_range(min_val: float, max_val: float, decimals: int = 2) -> float:
    return round(random.uniform(min_val, max_val), decimals)


def generate_player(
    player_id: str, role: PlayerRole, team_id: str | None, team_name: str | None
) -> dict:
    config = ROLE_CONFIGS[role]
    name = generate_player_name()
    entry_tc = (
        random_in_range(*config["entry_tc_range"])
        if "entry_tc_range" in config
        else None
    )
    exit_tc = (
        random_in_range(*config["exit_tc_range"]) if "exit_tc_range" in config else None
    )
    bankroll = random_in_range(*config["bankroll_range"])
    chosen_spread = random.choice(
        config.get("bet_spread_options", [config.get("bet_spread")])
    )

    return {
        "player_id": player_id,
        "player_name": name,
        "role": role.value,
        "team_id": team_id,
        "team_name": team_name,
        "bankroll": bankroll,
        "initial_bankroll": bankroll,
        "skill": random_in_range(*config["skill_range"]),
        "counting": random_in_range(*config["counting_range"]),
        "kelly_unit": random_in_range(*config["kelly_unit_range"], decimals=4),
        "bet_spread": (
            chosen_spread.copy() if isinstance(chosen_spread, dict) else chosen_spread
        ),
        "entry_tc": entry_tc,
        "exit_tc": exit_tc,
        "max_session_loss_pct": random_in_range(*config["max_session_loss_pct_range"]),
        "max_session_win_pct": random_in_range(*config["max_session_win_pct_range"]),
    }


def generate_team(team_id: str, team_name: str) -> List[dict]:
    team = []
    num_spotters = random.randint(2, 4)
    for i in range(num_spotters):
        team.append(
            generate_player(
                f"{team_id}_spotter_{i+1}", PlayerRole.SPOTTER, team_id, team_name
            )
        )

    team.append(
        generate_player(f"{team_id}_bp", PlayerRole.BIG_PLAYER, team_id, team_name)
    )

    if random.random() < 0.5:
        team.append(
            generate_player(
                f"{team_id}_bc", PlayerRole.BACK_COUNTER, team_id, team_name
            )
        )
    return team


def build_seed_data(num_players=15000, num_tables=1000):
    players = []
    total_weight = sum(config["weight"] for config in ROLE_CONFIGS.values())
    role_counts = {
        role: int(num_players * (config["weight"] / total_weight))
        for role, config in ROLE_CONFIGS.items()
    }

    num_teams = int(role_counts[PlayerRole.BIG_PLAYER] * 0.8)
    for team_idx in range(num_teams):
        team_id = f"TEAM_{team_idx+1:03d}"
        team_name = generate_team_name()
        if (
            role_counts[PlayerRole.SPOTTER] < 2
            or role_counts[PlayerRole.BIG_PLAYER] < 1
        ):
            break
        team = generate_team(team_id, team_name)
        players.extend(team)

        for p in team:
            role_enum = PlayerRole(p["role"])
            role_counts[role_enum] -= 1

    for role, count in role_counts.items():
        for i in range(count):
            players.append(generate_player(f"P_{len(players)+1:05d}", role, None, None))

    tables = []
    table_configs = [
        {"min": 25, "max": 500, "weight": 40},
        {"min": 50, "max": 1000, "weight": 30},
        {"min": 100, "max": 2500, "weight": 20},
        {"min": 500, "max": 5000, "weight": 10},
    ]
    for i in range(num_tables):
        config = random.choices(
            table_configs, weights=[c["weight"] for c in table_configs]
        )[0]
        tables.append(
            {
                "table_id": f"TABLE_{i+1:03d}",
                "table_min": config["min"],
                "table_max": config["max"],
                "num_decks": random.choice([6, 8]),
                "penetration": random_in_range(0.65, 0.80),
            }
        )

    return players, tables


def perform_seed():
    players, tables = build_seed_data()
    conn = None
    for attempt in range(30):
        try:
            conn = psycopg2.connect(
                host=os.getenv("DB_HOST", "timescaledb"),
                database=os.getenv("DB_NAME", "tablewatch"),
                user=os.getenv("DB_USER", "tablewatch"),
                password=os.getenv("DB_PASSWORD", "tablewatch"),
                port=os.getenv("DB_PORT", "5432"),
            )
            break
        except Exception as e:
            print(f"Waiting for DB (attempt {attempt + 1}/30): {e}")
            time.sleep(5)

    if not conn:
        raise Exception("DB Connection Failed")

    try:
        with conn.cursor() as cur:
            print("Cleaning Tables...")
            cur.execute("TRUNCATE players, tables CASCADE;")

            table_buf = io.StringIO()
            for t in tables:
                table_buf.write(
                    f"{t['table_id']}\t{t['table_min']}\t{t['table_max']}\t{t['num_decks']}\t{t['penetration']}\n"
                )
            table_buf.seek(0)
            cur.copy_from(
                table_buf,
                "tables",
                sep="\t",
                columns=(
                    "table_id",
                    "table_min",
                    "table_max",
                    "num_decks",
                    "penetration",
                ),
            )

            player_buf = io.StringIO()
            for p in players:

                def fmt(v):
                    return r"\N" if v is None else str(v)

                row = [
                    p["player_id"],
                    p["role"],
                    fmt(p["team_id"]),
                    str(p["bankroll"]),
                    str(p["initial_bankroll"]),
                    p["player_name"],
                    fmt(p["team_name"]),
                    str(p["skill"]),
                    str(p["counting"]),
                    str(p["kelly_unit"]),
                    json.dumps(p["bet_spread"]),
                    fmt(p["entry_tc"]),
                    fmt(p["exit_tc"]),
                    str(p["max_session_loss_pct"]),
                    str(p["max_session_win_pct"]),
                ]
                player_buf.write("\t".join(row) + "\n")
            player_buf.seek(0)
            cur.copy_from(
                player_buf,
                "players",
                sep="\t",
                null=r"\N",
                columns=(
                    "player_id",
                    "role",
                    "team_id",
                    "bankroll",
                    "initial_bankroll",
                    "player_name",
                    "team_name",
                    "skill",
                    "counting",
                    "kelly_unit",
                    "bet_spread",
                    "entry_tc",
                    "exit_tc",
                    "max_session_loss_pct",
                    "max_session_win_pct",
                ),
            )

            conn.commit()
            print("Seeding and Cron Setup Successful.")

    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Error: {e}")
        raise
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    perform_seed()
