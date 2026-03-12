UPDATE players
SET kelly_unit = LEAST(kelly_unit * 1.2, 0.03),
updated_at = NOW()
WHERE team_id = %s