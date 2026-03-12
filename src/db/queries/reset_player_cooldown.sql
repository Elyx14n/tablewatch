UPDATE players
SET
	is_active = true,
	cooldown_until = NULL,
	backoff_reason = NULL,
	updated_at = NOW()
WHERE is_active = false
	AND cooldown_until IS NOT NULL
	AND cooldown_until < NOW()