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
    role VARCHAR(20) NOT NULL,
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
    player_ids TEXT [],
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
    win_rate DECIMAL(5, 4),
    q1 DECIMAL(5, 4),
    q3 DECIMAL(5, 4),
    iqr DECIMAL(5, 4),
    bet_change_rate DECIMAL(5, 4),
    wonging_score DECIMAL(3, 2),
    team_correlation DECIMAL(3, 2),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (player_id, anomaly_type, anomaly_detected_at)
);
CREATE TABLE IF NOT EXISTS player_correlations (
    player_id_1 TEXT NOT NULL,
    player_id_2 TEXT NOT NULL,
    correlation DECIMAL(3, 2) NOT NULL,
    is_actual_team BOOLEAN,
    window_end TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (player_id_1, player_id_2, window_end)
);
SELECT create_hypertable(
        'player_correlations',
        'window_end',
        if_not_exists => TRUE
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
    player_ids TEXT []
);
CREATE INDEX idx_detected_teams_date ON detected_teams(detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_anomalies_player ON player_anomalies(player_id, anomaly_detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_anomalies_type ON player_anomalies(anomaly_type, anomaly_detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_anomalies_confidence ON player_anomalies(anomaly_confidence DESC)
WHERE anomaly_confidence > 0.75;
CREATE INDEX idx_correlations_p1 ON player_correlations(player_id_1, correlation DESC);
CREATE INDEX idx_correlations_p2 ON player_correlations(player_id_2, correlation DESC);