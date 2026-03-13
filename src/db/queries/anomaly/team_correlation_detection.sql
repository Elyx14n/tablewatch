INSERT INTO player_correlations WITH PlayerBets AS (
		SELECT player_id,
			team_id,
			table_id,
			window_start,
			window_end,
			AVG(bet_amount) as avg_bet,
			STDDEV(bet_amount) as stddev_bet,
			COUNT(*) as bet_count
		FROM TABLE(
				HOP(
					TABLE bet_events,
					DESCRIPTOR(event_time),
					INTERVAL '5' MINUTES,
					INTERVAL '1' HOUR
				)
			)
		GROUP BY player_id,
			team_id,
			table_id,
			window_start,
			window_end
		HAVING COUNT(*) >= 20
	),
	PairwiseCorrelations AS (
		SELECT p1.player_id as player_id_1,
			p2.player_id as player_id_2,
			p1.team_id as team_id_1,
			p2.team_id as team_id_2,
			p1.window_end,
			(
				SUM(
					(p1.avg_bet - AVG(p1.avg_bet) OVER w1) * (p2.avg_bet - AVG(p2.avg_bet) OVER w2)
				) / NULLIF(
					STDDEV(p1.avg_bet) OVER w1 * STDDEV(p2.avg_bet) OVER w2,
					0
				)
			) as correlation
		FROM PlayerBets p1
			INNER JOIN PlayerBets p2 ON p1.window_end = p2.window_end
			AND p1.player_id < p2.player_id WINDOW w1 AS (
				PARTITION BY p1.player_id
				ORDER BY p1.window_end ROWS BETWEEN 11 PRECEDING AND CURRENT ROW
			),
			w2 AS (
				PARTITION BY p2.player_id
				ORDER BY p2.window_end ROWS BETWEEN 11 PRECEDING AND CURRENT ROW
			)
	)
SELECT player_id_1,
	player_id_2,
	correlation,
	window_end,
	CASE
		WHEN correlation > 0.85 THEN 'VERY_HIGH'
		WHEN correlation > 0.75 THEN 'HIGH'
		ELSE 'MODERATE'
	END as correlation_level,
	(team_id_1 = team_id_2) as is_actual_team
FROM PairwiseCorrelations
WHERE correlation > 0.7;