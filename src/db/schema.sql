CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;
CREATE TABLE IF NOT EXISTS tables (
  table_id TEXT PRIMARY KEY,
  table_min DECIMAL(10, 2) DEFAULT 25.0,
  table_max DECIMAL(10, 2) DEFAULT 5000.0,
  num_decks INT DEFAULT 6,
  penetration DECIMAL(3, 2) DEFAULT 0.65,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS players (
  player_id TEXT PRIMARY KEY,
  player_name TEXT,
  ROLE VARCHAR(20) NOT NULL,
  team_id TEXT,
  team_name TEXT,
  bankroll DECIMAL(12, 2) NOT NULL,
  initial_bankroll DECIMAL(12, 2) NOT NULL,
  skill DECIMAL(3, 2) DEFAULT 1.0,
  counting DECIMAL(3, 2) DEFAULT 0.0,
  kelly_unit DECIMAL(5, 4) DEFAULT 0.0,
  bet_spread JSONB,
  entry_tc DECIMAL(4, 2),
  exit_tc DECIMAL(4, 2),
  max_session_loss_pct DECIMAL(3, 2) DEFAULT 0.5,
  max_session_win_pct DECIMAL(3, 2) DEFAULT 1.0,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS games (
  game_id TEXT PRIMARY KEY,
  table_id TEXT NOT NULL REFERENCES tables(table_id),
  started_at TIMESTAMPTZ NOT NULL,
  ended_at TIMESTAMPTZ,
  duration_seconds INTEGER GENERATED ALWAYS AS (
    EXTRACT(
      EPOCH
      FROM (ended_at - started_at)
    )::INTEGER
  ) STORED,
  num_decks INTEGER,
  penetration DECIMAL(3, 2),
  table_min DECIMAL(10, 2),
  table_max DECIMAL(10, 2),
  player_ids TEXT [ ],
  initial_player_count INTEGER,
  final_player_count INTEGER,
  total_hands INTEGER DEFAULT 0,
  total_shuffles INTEGER DEFAULT 0,
  total_bets_placed DECIMAL(15, 2) DEFAULT 0,
  total_payouts DECIMAL(15, 2) DEFAULT 0,
  house_edge_realized DECIMAL(5, 4),
  anomalies_detected INTEGER DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_games_table ON games(table_id);
CREATE INDEX idx_games_started ON games(started_at DESC);
CREATE INDEX idx_games_duration ON games(duration_seconds)
WHERE duration_seconds IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_players_team ON players(team_id);
CREATE TABLE IF NOT EXISTS player_anomalies (
  player_id TEXT NOT NULL,
  anomaly_type TEXT NOT NULL,
  anomaly_confidence DECIMAL(3, 2) NOT NULL,
  anomaly_detected_at TIMESTAMPTZ NOT NULL,
  bet_spread DECIMAL(8, 2),
  z_score DECIMAL(8, 4),
  bet_change_rate DECIMAL(5, 4),
  wonging_score DECIMAL(3, 2),
  count_corr DECIMAL(8, 4),
  team_correlation DECIMAL(3, 2),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (player_id, anomaly_type, anomaly_detected_at)
);
SELECT create_hypertable(
    'player_anomalies',
    'anomaly_detected_at',
    if_not_exists => TRUE
  );
CREATE TABLE IF NOT EXISTS detected_teams (
  detected_team_id TEXT PRIMARY KEY,
  member_count INT,
  team_correlation DECIMAL(3, 2),
  detected_at TIMESTAMPTZ DEFAULT NOW(),
  team_name TEXT,
  player_ids TEXT [ ]
);
CREATE INDEX idx_detected_teams_date ON detected_teams(detected_at DESC);
CREATE TABLE IF NOT EXISTS game_events (
  event_id TEXT NOT NULL,
  event_time TIMESTAMPTZ NOT NULL,
  table_id TEXT NOT NULL,
  round_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  player_id TEXT,
  summary TEXT,
  bankroll_after DECIMAL(12,2),
  PRIMARY KEY (event_id, event_time)
);
SELECT create_hypertable(
    'game_events',
    'event_time',
    if_not_exists => TRUE
  );
CREATE INDEX idx_game_events_table_time ON game_events(table_id, event_time DESC);
CREATE INDEX IF NOT EXISTS idx_anomalies_player ON player_anomalies(player_id, anomaly_detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_anomalies_type ON player_anomalies(anomaly_type, anomaly_detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_anomalies_confidence ON player_anomalies(anomaly_confidence DESC)
WHERE anomaly_confidence > 0.75;