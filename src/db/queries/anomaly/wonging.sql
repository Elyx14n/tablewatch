INSERT INTO player_anomalies WITH
	PlayerSessions AS (
		SELECT player_id,
			true_count as entry_count,
			event_time,
			ROW_NUMBER() OVER (
				PARTITION BY player_id,
				window_start
				ORDER BY event_time ASC
			) as bet_sequence
		FROM TABLE(
				SESSION(
					TABLE bet_events,
					DESCRIPTOR(event_time),
					INTERVAL '20' MINUTES
				)
			)
	),
	EntriesOnly AS (
		SELECT player_id,
			entry_count,
			event_time
		FROM PlayerSessions
		WHERE bet_sequence = 1
	),
	WongingAnalysis AS (
		SELECT player_id,
			event_time,
			entry_count,
			AVG(entry_count) OVER w AS avg_entry_count,
			STDDEV(entry_count) OVER w AS stddev_entry_count
		FROM EntriesOnly WINDOW w AS (
				PARTITION BY player_id
				ORDER BY event_time ROWS BETWEEN 10 PRECEDING AND CURRENT ROW
			)
	)
SELECT player_id,
	'WONGING_ENTRY_ANOMALY' AS anomaly_type,
	LEAST(avg_entry_count / 5.0, 1.0) AS anomaly_confidence,
	event_time AS anomaly_detected_at,
	avg_entry_count AS wonging_score
FROM WongingAnalysis
WHERE avg_entry_count > 3.0
	AND stddev_entry_count < 1.5