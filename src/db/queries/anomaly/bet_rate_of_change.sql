INSERT INTO player_anomalies WITH WindowedBets AS (
		SELECT player_id,
			window_end,
			AVG(bet_amount) AS avg_bet_amount,
			COUNT(*) as hand_count
		FROM TABLE(
				HOP(
					TABLE bet_events,
					DESCRIPTOR(event_time),
					INTERVAL '5' MINUTES,
					INTERVAL '30' MINUTES
				)
			)
		GROUP BY player_id,
			window_start,
			window_end
		HAVING COUNT(*) >= 10
	),
	BetVelocity AS (
		SELECT player_id,
			window_end,
			avg_bet_amount,
			(avg_bet_amount - LAG(avg_bet_amount, 1) OVER w) / NULLIF(LAG(avg_bet_amount, 1) OVER w, 0) AS rate_of_change
		FROM WindowedBets WINDOW w AS (
				PARTITION BY player_id
				ORDER BY window_end
			)
	),
	VelocityScoring AS (
		SELECT player_id,
			window_end,
			rate_of_change,
			AVG(rate_of_change) OVER population AS avg_roc,
			STDDEV(rate_of_change) OVER population AS stddev_roc
		FROM BetVelocity WINDOW population AS (
				PARTITION BY player_id
				ORDER BY window_end ROWS BETWEEN 24 PRECEDING AND CURRENT ROW -- Look at the last 2 hours of change
			)
	)
SELECT player_id,
	'BET_VELOCITY_SPIKE' AS anomaly_type,
	LEAST(
		ABS(
			(rate_of_change - avg_roc) / NULLIF(stddev_roc, 0)
		) / 5.0,
		1.0
	) AS anomaly_confidence,
	window_end AS anomaly_detected_at,
	rate_of_change AS bet_change_rate,
	(rate_of_change - avg_roc) / NULLIF(stddev_roc, 0) AS z_score
FROM VelocityScoring
WHERE (rate_of_change - avg_roc) / NULLIF(stddev_roc, 0) > 3.0
	AND rate_of_change > 1.0