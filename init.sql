CREATE EXTENSION IF NOT EXISTS pg_cron;
SELECT cron.schedule(
        'team-network-detection',
        '*/30 * * * *',
        $$ WITH RECURSIVE team_network AS (
            -- ANCHOR: Start with direct high-correlation pairs (1st degree connections)
            SELECT player_id_1 as player_id,
                player_id_2 as connected_player,
                1 as depth,
                correlation,
                ARRAY [player_id_1, player_id_2] as path
            FROM player_correlations
            WHERE window_end > NOW() - INTERVAL '6 hours'
                AND correlation > 0.80
            UNION ALL
            -- RECURSIVE: Follow the chain to find indirect connections (2nd/3rd degree)
            SELECT tn.player_id,
                pc.player_id_2 as connected_player,
                tn.depth + 1,
                pc.correlation,
                tn.path || pc.player_id_2
            FROM team_network tn
                JOIN player_correlations pc ON tn.connected_player = pc.player_id_1
            WHERE tn.depth < 3
                AND pc.window_end > NOW() - INTERVAL '6 hours'
                AND pc.correlation > 0.70
                AND NOT (pc.player_id_2 = ANY(tn.path))
        ),
        network_summary AS (
            SELECT player_id,
                COUNT(DISTINCT connected_player) as network_size,
                AVG(correlation) as avg_correlation,
                MAX(depth) as max_depth
            FROM team_network
            GROUP BY player_id
            HAVING COUNT(DISTINCT connected_player) >= 2
        )
        INSERT INTO player_anomalies (
                player_id,
                anomaly_type,
                anomaly_confidence,
                anomaly_detected_at,
                team_correlation
            )
        SELECT player_id,
            'TEAM_COLLUSION_NETWORK' as anomaly_type,
            LEAST(network_size / 5.0, 1.0) as anomaly_confidence,
            NOW() as anomaly_detected_at,
            avg_correlation as team_correlation
        FROM network_summary ON CONFLICT (player_id, anomaly_type, anomaly_detected_at) DO NOTHING;
$$
);
DO $$ BEGIN RAISE NOTICE 'pg_cron setup complete: Team network detection scheduled every 30 minutes';
END $$;