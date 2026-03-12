-- Detect players with high bet spreads (suspected card counters)
-- Returns: player_id, bet_spread
WITH bet_stats AS (
    SELECT
        player_id,
        MIN(bet_amount) as min_bet,
        MAX(bet_amount) as max_bet,
        COUNT(*) as hand_count
    FROM bet_events
    WHERE timestamp > NOW() - INTERVAL '1 hour'
    GROUP BY player_id
    HAVING COUNT(*) >= 20
)
SELECT
    player_id,
    max_bet / NULLIF(min_bet, 0) as bet_spread
FROM bet_stats
WHERE max_bet / NULLIF(min_bet, 0) > 10;