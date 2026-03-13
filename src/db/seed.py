import random
import json
from pathlib import Path
from typing import List, Tuple
from blackjack.strategy import PlayerRole

FIRST_NAMES = [
    "James", "Michael", "Robert", "John", "David", "William", "Richard", "Joseph", "Thomas", "Christopher",
    "Mary", "Patricia", "Jennifer", "Linda", "Barbara", "Elizabeth", "Susan", "Jessica", "Sarah", "Karen",
    "Daniel", "Matthew", "Anthony", "Mark", "Donald", "Steven", "Andrew", "Paul", "Joshua", "Kenneth",
    "Nancy", "Lisa", "Betty", "Margaret", "Sandra", "Ashley", "Kimberly", "Emily", "Donna", "Michelle",
    "Kevin", "Brian", "George", "Timothy", "Ronald", "Edward", "Jason", "Jeffrey", "Ryan", "Jacob",
    "Carol", "Amanda", "Melissa", "Deborah", "Stephanie", "Dorothy", "Rebecca", "Sharon", "Laura", "Cynthia",
    "Eric", "Nicholas", "Samuel", "Benjamin", "Gregory", "Alexander", "Frank", "Patrick", "Raymond", "Jack",
    "Kathleen", "Amy", "Angela", "Shirley", "Anna", "Brenda", "Pamela", "Emma", "Nicole", "Helen",
    "Dennis", "Jerry", "Tyler", "Aaron", "Jose", "Adam", "Nathan", "Henry", "Douglas", "Zachary",
    "Virginia", "Katherine", "Christine", "Samantha", "Debra", "Janet", "Catherine", "Carolyn", "Ruth", "Maria"
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez",
    "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
    "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson",
    "Walker", "Young", "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores",
    "Green", "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell", "Carter", "Roberts",
    "Gomez", "Phillips", "Evans", "Turner", "Diaz", "Parker", "Cruz", "Edwards", "Collins", "Reyes",
    "Stewart", "Morris", "Morales", "Murphy", "Cook", "Rogers", "Gutierrez", "Ortiz", "Morgan", "Cooper",
    "Peterson", "Bailey", "Reed", "Kelly", "Howard", "Ramos", "Kim", "Cox", "Ward", "Richardson",
    "Watson", "Brooks", "Chavez", "Wood", "James", "Bennett", "Gray", "Mendoza", "Ruiz", "Hughes",
    "Price", "Alvarez", "Castillo", "Sanders", "Patel", "Myers", "Long", "Ross", "Foster", "Jimenez"
]

ROLE_CONFIGS = {
    PlayerRole.CASUAL: {
        "skill_range": (0.85, 0.98),
        "counting_range": (0.0, 0.0),
        "kelly_unit_range": (0.0, 0.0),
        "bet_spread": {"1": 1, "2": 1, "3": 1},
        "bankroll_range": (500, 3000),
        "max_session_loss_pct_range": (0.3, 0.7),
        "max_session_win_pct_range": (0.8, 1.5),
        "entry_tc": None,
        "exit_tc": None,
        "weight": 60,
    },
    PlayerRole.ADVANTAGE: {
        "skill_range": (0.98, 1.0),
        "counting_range": (0.7, 0.95),
        "kelly_unit_range": (0.005, 0.02),
        "bet_spread_options": [
            {"1": 1, "2": 4, "3": 8},
            {"1": 1, "2": 5, "3": 10},
            {"1": 1, "2": 6, "3": 12},
        ],
        "bankroll_range": (5000, 25000),
        "max_session_loss_pct_range": (0.4, 0.6),
        "max_session_win_pct_range": (1.0, 2.0),
        "entry_tc": None,
        "exit_tc": None,
        "weight": 25,
    },
    PlayerRole.SPOTTER: {
        "skill_range": (0.95, 1.0),
        "counting_range": (0.85, 1.0),
        "kelly_unit_range": (0.001, 0.005),
        "bet_spread": {"1": 1, "2": 1, "3": 2},
        "bankroll_range": (2000, 8000),
        "max_session_loss_pct_range": (0.5, 0.7),
        "max_session_win_pct_range": (0.5, 1.0),
        "entry_tc": None,  # Spotters sit at table continuously
        "exit_tc": None,
        "weight": 8,
    },
    PlayerRole.BIG_PLAYER: {
        "skill_range": (0.98, 1.0),
        "counting_range": (0.0, 0.3),
        "kelly_unit_range": (0.02, 0.05),
        "bet_spread_options": [
            {"1": 10, "2": 20, "3": 50},
            {"1": 15, "2": 30, "3": 75},
            {"1": 20, "2": 40, "3": 100},
        ],
        "bankroll_range": (30000, 100000),
        "max_session_loss_pct_range": (0.3, 0.5),
        "max_session_win_pct_range": (1.5, 3.0),
        "entry_tc_range": (0.5, 1.5),  # Big players enter on positive counts
        "exit_tc_range": (-1.5, -0.5),  # Exit when count goes negative
        "weight": 4,  # 4% of players
    },
    PlayerRole.BACK_COUNTER: {
        "skill_range": (0.98, 1.0),
        "counting_range": (0.9, 1.0),
        "kelly_unit_range": (0.015, 0.035),
        "bet_spread_options": [
            {"1": 1, "2": 8, "3": 16},
            {"1": 1, "2": 10, "3": 20},
        ],
        "bankroll_range": (15000, 50000),
        "max_session_loss_pct_range": (0.4, 0.6),
        "max_session_win_pct_range": (1.2, 2.5),
        "entry_tc_range": (1.5, 2.5),  # Back counters enter on higher counts
        "exit_tc_range": (-0.5, 0.5),  # Exit when count drops to neutral/negative
        "weight": 3,
    },
}


def generate_player_name(used_names: set) -> str:
    attempts = 0
    first, last = "", ""
    while attempts < 1000:
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        name = f"{first} {last}"
        if name not in used_names:
            used_names.add(name)
            return name
        attempts += 1
    middle = chr(random.randint(65, 90))
    name = f"{first} {middle}. {last}"
    used_names.add(name)
    return name


def random_in_range(min_val: float, max_val: float, decimals: int = 2) -> float:
    return round(random.uniform(min_val, max_val), decimals)


def generate_player(
    player_id: str,
    role: PlayerRole,
    team_id: str | None,
    used_names: set
) -> Tuple[str, dict]:
    config = ROLE_CONFIGS[role]
    name = generate_player_name(used_names)

    skill = random_in_range(*config["skill_range"])
    counting = random_in_range(*config["counting_range"])
    kelly_unit = random_in_range(*config["kelly_unit_range"], decimals=4)

    if "bet_spread_options" in config:
        bet_spread = random.choice(config["bet_spread_options"])
    else:
        bet_spread = config["bet_spread"]

    bankroll = random_in_range(*config["bankroll_range"], decimals=2)

    max_session_loss_pct = random_in_range(*config["max_session_loss_pct_range"])
    max_session_win_pct = random_in_range(*config["max_session_win_pct_range"])

    if "entry_tc_range" in config:
        entry_tc = random_in_range(*config["entry_tc_range"])
    else:
        entry_tc = config.get("entry_tc")  # None for non-wonging roles

    if "exit_tc_range" in config:
        exit_tc = random_in_range(*config["exit_tc_range"])
    else:
        exit_tc = config.get("exit_tc")  # None for non-wonging roles

    return name, {
        "player_id": player_id,
        "role": role.value,
        "team_id": team_id,
        "bankroll": bankroll,
        "initial_bankroll": bankroll,
        "skill": skill,
        "counting": counting,
        "kelly_unit": kelly_unit,
        "bet_spread": bet_spread,
        "entry_tc": entry_tc,
        "exit_tc": exit_tc,
        "max_session_loss_pct": max_session_loss_pct,
        "max_session_win_pct": max_session_win_pct,
    }


def generate_team(team_id: str, used_names: set) -> List[dict]:
    team = []

    num_spotters = random.randint(2, 4)
    for i in range(num_spotters):
        _, player = generate_player(
            f"{team_id}_spotter_{i+1}",
            PlayerRole.SPOTTER,
            team_id,
            used_names
        )
        team.append(player)

    _, player = generate_player(
        f"{team_id}_bp",
        PlayerRole.BIG_PLAYER,
        team_id,
        used_names
    )
    team.append(player)

    if random.random() < 0.5:
        _, player = generate_player(
            f"{team_id}_bc",
            PlayerRole.BACK_COUNTER,
            team_id,
            used_names
        )
        team.append(player)

    return team


def generate_players(num_players: int = 5000) -> List[dict]:
    players = []
    used_names = set()

    total_weight = sum(config["weight"] for config in ROLE_CONFIGS.values())

    role_counts = {
        role: int(num_players * (config["weight"] / total_weight))
        for role, config in ROLE_CONFIGS.items()
    }

    team_roles_needed = {
        PlayerRole.SPOTTER: role_counts[PlayerRole.SPOTTER],
        PlayerRole.BIG_PLAYER: role_counts[PlayerRole.BIG_PLAYER],
        PlayerRole.BACK_COUNTER: role_counts[PlayerRole.BACK_COUNTER],
    }

    total_team_players = sum(team_roles_needed.values())
    num_teams = int(total_team_players / 4.5)

    for team_idx in range(num_teams):
        team_id = f"TEAM_{team_idx+1:03d}"
        team = generate_team(team_id, used_names)
        players.extend(team)

    num_casual = role_counts[PlayerRole.CASUAL]
    num_advantage = role_counts[PlayerRole.ADVANTAGE]

    for _ in range(num_casual):
        _, player = generate_player(
            f"P_{len(players)+1:05d}",
            PlayerRole.CASUAL,
            None,
            used_names
        )
        players.append(player)

    for _ in range(num_advantage):
        _, player = generate_player(
            f"P_{len(players)+1:05d}",
            PlayerRole.ADVANTAGE,
            None,
            used_names
        )
        players.append(player)

    return players


def generate_tables(num_tables: int = 80) -> List[dict]:
    tables = []
    table_configs = [
        {"min": 25, "max": 500, "weight": 40},    # Low stakes
        {"min": 50, "max": 1000, "weight": 30},   # Mid stakes
        {"min": 100, "max": 2500, "weight": 20},  # High stakes
        {"min": 500, "max": 5000, "weight": 10},  # VIP stakes
    ]

    for i in range(num_tables):
        config = random.choices(
            table_configs,
            weights=[c["weight"] for c in table_configs]
        )[0]
        num_decks = random.choice([6, 6, 6, 8, 8])
        penetration = random_in_range(0.65, 0.80)
        tables.append({
            "table_id": f"TABLE_{i+1:03d}",
            "table_min": config["min"],
            "table_max": config["max"],
            "num_decks": num_decks,
            "penetration": penetration,
        })

    return tables


def generate_sql(players: List[dict], tables: List[dict]) -> str:
    sql_lines = ["TRUNCATE players, tables CASCADE;"]
    for table in tables:
        sql_lines.append(
            f"INSERT INTO tables (table_id, table_min, table_max, num_decks, penetration) "
            f"VALUES ('{table['table_id']}', {table['table_min']}, {table['table_max']}, "
            f"{table['num_decks']}, {table['penetration']});"
        )

    for player in players:
        bet_spread_dict = {int(k): v for k, v in player["bet_spread"].items()}
        bet_spread_json = json.dumps(bet_spread_dict)
        team_id = f"'{player['team_id']}'" if player['team_id'] else "NULL"
        entry_tc = player['entry_tc'] if player['entry_tc'] is not None else "NULL"
        exit_tc = player['exit_tc'] if player['exit_tc'] is not None else "NULL"

        sql_lines.append(
            f"INSERT INTO players (player_id, role, team_id, bankroll, initial_bankroll, "
            f"skill, counting, kelly_unit, bet_spread, entry_tc, exit_tc, "
            f"max_session_loss_pct, max_session_win_pct) "
            f"VALUES ('{player['player_id']}', '{player['role']}', {team_id}, "
            f"{player['bankroll']}, {player['initial_bankroll']}, {player['skill']}, "
            f"{player['counting']}, {player['kelly_unit']}, '{bet_spread_json}'::jsonb, "
            f"{entry_tc}, {exit_tc}, "
            f"{player['max_session_loss_pct']}, {player['max_session_win_pct']});"
        )

    return "\n".join(sql_lines)


def generate_statistics(players: List[dict]) -> str:
    role_counts, team_counts = {}, {}
    for player in players:
        role = player["role"]
        role_counts[role] = role_counts.get(role, 0) + 1

        if player["team_id"]:
            team_counts[player["team_id"]] = team_counts.get(player["team_id"], 0) + 1

    stats = [
        f"\nPlayer Distribution Statistics:",
        f"Total Players: {len(players)}",
        f"",
        f"By Role:",
    ]

    for role, count in sorted(role_counts.items()):
        pct = (count / len(players)) * 100
        stats.append(f"  {role}: {count} ({pct:.1f}%)")

    stats.extend([
        f"",
        f"Teams: {len(team_counts)}",
        f"Players in Teams: {sum(team_counts.values())}",
        f"Solo Players: {len(players) - sum(team_counts.values())}",
    ])

    return "\n".join(stats)


if __name__ == "__main__":
    print("Generating seed data...")
    players = generate_players(num_players=15000)
    tables = generate_tables(num_tables=1000)
    print(generate_statistics(players))
    sql = generate_sql(players, tables)
    output_path = Path(__file__).parent / "seed_data.sql"
    output_path.write_text(sql, encoding="utf-8")
    print(f"\nSeed data written to: {output_path}")
    print(f"Total SQL statements: {len(players) + len(tables)}")
