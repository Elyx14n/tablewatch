INSERT INTO detected_teams (
        detected_team_id,
        member_count,
        team_correlation,
        team_detection_accuracy,
        actual_team_ids,
        actual_team_names,
        detected_at,
        team_name,
        player_ids
    )
WITH flagged AS (
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
        WHERE g1.player_id IN (SELECT player_id FROM flagged)
            AND g2.player_id IN (SELECT player_id FROM flagged)
            AND g1.event_time >= NOW() - INTERVAL '2 hours'
        GROUP BY 1, 2
        HAVING COUNT(DISTINCT g1.round_id) >= 10
    ),
    clusters AS (
        SELECT 'TEAM_' || player_1 AS detected_team_id,
            COUNT(DISTINCT player_2) + 1 AS member_count,
            LEAST(ROUND(AVG(shared_rounds) / 50.0, 2), 1.0) AS team_correlation,
            NOW() AS detected_at,
            'AP_CLUSTER_' || player_1 AS team_name,
            ARRAY [player_1] || ARRAY_AGG(DISTINCT player_2) AS player_ids
        FROM shared_tables
        GROUP BY player_1
    ),
    accuracy AS (
        SELECT c.detected_team_id,
            ROUND(
                COUNT(p.player_id) FILTER (WHERE p.team_id IS NOT NULL)::DECIMAL
                / NULLIF(ARRAY_LENGTH(c.player_ids, 1), 0),
                4
            ) AS team_detection_accuracy,
            ARRAY_AGG(DISTINCT p.team_id)   FILTER (WHERE p.team_id IS NOT NULL) AS actual_team_ids,
            ARRAY_AGG(DISTINCT p.team_name) FILTER (WHERE p.team_name IS NOT NULL) AS actual_team_names
        FROM clusters c
            JOIN LATERAL unnest(c.player_ids) AS pid ON true
            LEFT JOIN players p ON p.player_id = pid
        GROUP BY c.detected_team_id, c.player_ids
    )
SELECT c.detected_team_id,
    c.member_count,
    c.team_correlation,
    a.team_detection_accuracy,
    a.actual_team_ids,
    a.actual_team_names,
    c.detected_at,
    c.team_name,
    c.player_ids
FROM clusters c
JOIN accuracy a ON c.detected_team_id = a.detected_team_id
ON CONFLICT (detected_team_id) DO UPDATE
SET member_count = EXCLUDED.member_count,
    team_correlation = EXCLUDED.team_correlation,
    team_detection_accuracy = EXCLUDED.team_detection_accuracy,
    actual_team_ids = EXCLUDED.actual_team_ids,
    actual_team_names = EXCLUDED.actual_team_names,
    detected_at = EXCLUDED.detected_at,
    player_ids = EXCLUDED.player_ids
