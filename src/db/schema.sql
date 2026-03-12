CREATE TABLE IF NOT EXISTS tables (
    table_id VARCHAR(50) PRIMARY KEY,
    table_min DECIMAL(10, 2) DEFAULT 25.0,
    table_max DECIMAL(10, 2) DEFAULT 5000.0,
    num_decks INT DEFAULT 6,
    penetration DECIMAL(3, 2) DEFAULT 0.65,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS players (
    player_id VARCHAR(50) PRIMARY KEY,
    role VARCHAR(20) NOT NULL,
    team_id VARCHAR(50),
    -- Bankroll
    bankroll DECIMAL(12, 2) NOT NULL,
    initial_bankroll DECIMAL(12, 2) NOT NULL,
    -- Strategy params
    skill DECIMAL(3, 2) DEFAULT 1.0,
    counting DECIMAL(3, 2) DEFAULT 0.0,
    kelly_unit DECIMAL(5, 4) DEFAULT 0.0,
    bet_spread JSONB,
    -- Session limits
    max_session_loss_pct DECIMAL(3, 2) DEFAULT 0.5,
    max_session_win_pct DECIMAL(3, 2) DEFAULT 1.0,
    -- Player status
    is_active BOOLEAN DEFAULT TRUE,
    cooldown_until TIMESTAMP,
    backoff_reason VARCHAR(50),
    -- Anomaly data
    anomaly_detected BOOLEAN DEFAULT FALSE anomaly_type VARCHAR(50) anomaly_confidence DECIMAL(3, 2) anomaly_detected_at TIMESTAMP -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS team_configs (
    team_id VARCHAR(50) PRIMARY KEY,
    target_profit DECIMAL(12, 2) DEFAULT 0,
    stop_loss DECIMAL(12, 2) DEFAULT 0,
    current_session_pl DECIMAL(12, 2) DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    updated_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS games (
    -- Identity
    game_id VARCHAR(50) PRIMARY KEY,
    table_id VARCHAR(50) NOT NULL REFERENCES tables(table_id),
    -- Timing
    started_at TIMESTAMP NOT NULL,
    ended_at TIMESTAMP,
    duration_seconds INTEGER GENERATED ALWAYS AS (
        EXTRACT(
            EPOCH
            FROM (ended_at - started_at)
        )::INTEGER
    ) STORED,
    -- Game metadata
    num_decks INTEGER,
    penetration DECIMAL(3, 2),
    table_min DECIMAL(10, 2),
    table_max DECIMAL(10, 2),
    -- Player tracking
    player_ids TEXT [],
    -- Array of player_id strings
    initial_player_count INTEGER,
    final_player_count INTEGER,
    -- Game statistics (derived/computed)
    total_hands INTEGER DEFAULT 0,
    total_shuffles INTEGER DEFAULT 0,
    total_bets_placed DECIMAL(15, 2) DEFAULT 0,
    total_payouts DECIMAL(15, 2) DEFAULT 0,
    house_edge_realized DECIMAL(5, 4),
    -- Anomaly summary
    anomalies_detected INTEGER DEFAULT 0,
    backoffs_issued INTEGER DEFAULT 0,
    -- Status
    termination_reason VARCHAR(50),
    -- 'ALL_PLAYERS_QUIT', 'BACKOFF', 'SHUTDOWN', etc.
    -- Indexes
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_games_table ON games(table_id);
CREATE INDEX idx_games_started ON games(started_at DESC);
CREATE INDEX idx_games_duration ON games(duration_seconds)
WHERE duration_seconds IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_players_team ON players(team_id);
CREATE INDEX IF NOT EXISTS idx_players_active ON players(is_active);
CREATE INDEX IF NOT EXISTS idx_players_cooldown ON players(cooldown_until)
WHERE cooldown_until IS NOT NULL;