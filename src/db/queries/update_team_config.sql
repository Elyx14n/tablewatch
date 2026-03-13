INSERT INTO team_configs (team_id, current_session_pl, updated_at)
VALUES (%s, %s, NOW()) ON CONFLICT (team_id) DO
UPDATE
SET current_session_pl = EXCLUDED.current_session_pl,
	updated_at = NOW()