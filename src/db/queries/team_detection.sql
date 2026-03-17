INSERT INTO detected_teams (
        detected_team_id,
        member_count,
        team_correlation,
        detected_at,
        team_name,
        player_ids
    ) WITH flagged AS (
        SELECT DISTINCT player_id
        FROM player_anomalies
        WHERE anomaly_type IN ('CARD_COUNTING', 'WONGING_ENTRY_ANOMALY')
            AND anomaly_detected_at >= NOW() - INTERVAL '2 hours'
    ),
    shared_tables AS (
        SELECT LEAST(g1.player_id, g2.player_id) AS player_1,
            GREATEST(g1.player_id, g2.player_id) AS player_2,
            COUNT(DISTINCT g1.round_id) AS shared_rounds
        FROM game_events g1
            JOIN game_events g2 ON g1.table_id = g2.table_id
            AND g1.round_id = g2.round_id
            AND g1.player_id < g2.player_id
            AND g1.event_type = 'BET'
            AND g2.event_type = 'BET'
        WHERE g1.player_id IN (
                SELECT player_id
                FROM flagged
            )
            AND g2.player_id IN (
                SELECT player_id
                FROM flagged
            )
            AND g1.event_time >= NOW() - INTERVAL '2 hours'
        GROUP BY 1,
            2
        HAVING COUNT(DISTINCT g1.round_id) >= 10
    )
SELECT 'TEAM_' || player_1 AS detected_team_id,
    COUNT(DISTINCT player_2) + 1 AS member_count,
    LEAST(ROUND(AVG(shared_rounds) / 50.0, 2), 1.0) AS team_correlation,
    NOW() AS detected_at,
    'AP_CLUSTER_' || player_1 AS team_name,
    ARRAY [player_1] || ARRAY_AGG(DISTINCT player_2) AS player_ids
FROM shared_tables
GROUP BY player_1 ON CONFLICT (detected_team_id) DO
UPDATE
SET member_count = EXCLUDED.member_count,
    team_correlation = EXCLUDED.team_correlation,
    detected_at = EXCLUDED.detected_at,
    player_ids = EXCLUDED.player_ids