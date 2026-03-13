INSERT INTO player_anomalies WITH
	PlayerStats AS (
		SELECT player_id,
			window_end,
			CAST(
				SUM(
					CASE
						WHEN result IN ('win', 'blackjack') THEN 1
						ELSE 0
					END
				) AS DOUBLE
			) / NULLIF(COUNT(*), 0) AS win_rate,
			COUNT(*) as hand_count
		FROM TABLE(
				HOP(
					TABLE outcome_events,
					DESCRIPTOR(event_time),
					INTERVAL '5' MINUTES,
					INTERVAL '4' HOURS
				)
			)
		GROUP BY player_id,
			window_start,
			window_end
		HAVING COUNT(*) >= 50
	),
	Percentiles AS (
		SELECT *,
			PERCENTILE_CONT(0.25) WITHIN GROUP (
				ORDER BY win_rate
			) OVER population AS q1,
			PERCENTILE_CONT(0.75) WITHIN GROUP (
				ORDER BY win_rate
			) OVER population AS q3
		FROM PlayerStats
			WINDOW population AS (
				ORDER BY window_end ROWS BETWEEN 500 PRECEDING AND CURRENT ROW
			)
	),
	Scoring AS (
		SELECT *,
			(q3 - q1) AS iqr,
			(q3 + 1.5 * (q3 - q1)) AS upper_fence
		FROM Percentiles
		WHERE win_rate > 0.55
	)
SELECT player_id,
	'IMPOSSIBLE_WIN_RATE_IQR' AS anomaly_type,
	LEAST((win_rate - upper_fence) / NULLIF(iqr, 0), 1.0) AS anomaly_confidence,
	window_end AS anomaly_detected_at,
	win_rate,
	q1,
	q3,
	iqr
FROM Scoring
WHERE win_rate > upper_fence