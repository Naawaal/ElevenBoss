-- Roll back live pitch feature flag (US-26/US-27 removed from bot).
-- Idempotent: no-op if live_pitch_enabled was never seeded.

DELETE FROM public.game_config WHERE key = 'live_pitch_enabled';
