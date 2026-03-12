-- Get team profit/loss performance over last 24 hours
-- Returns: team_id, total_pl, hand_count
SELECT
    team_id,
    SUM(payout) as total_pl,
    COUNT(*) as hand_count
FROM outcome_events
WHERE team_id IS NOT NULL
  AND timestamp > NOW() - INTERVAL '24 hours'
GROUP BY team_id;