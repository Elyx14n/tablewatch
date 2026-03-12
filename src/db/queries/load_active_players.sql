-- Load active players that are not on cooldown
SELECT
    player_id, role, team_id, bankroll, initial_bankroll,
    skill, counting, kelly_unit, bet_spread,
    max_session_loss_pct, max_session_win_pct
FROM players
WHERE is_active = true
  AND (cooldown_until IS NULL OR cooldown_until < NOW());
