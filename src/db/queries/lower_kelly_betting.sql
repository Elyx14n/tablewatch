UPDATE players
SET kelly_unit = kelly_unit * 0.8,
	updated_at = NOW()
WHERE team_id = %s