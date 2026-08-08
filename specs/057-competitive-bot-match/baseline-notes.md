# Baseline notes — Competitive Bot Match (057)

Captured at Feature 057 implement start (post-056 shelve).

## Flag-off Bot Battle (production default)

- Stream: NSS v2/v3 via `stream_match` / `stream_match_v3`; regulation ends at minute 90 with `FULL_TIME`.
- Stadium cadence: ticker sleeps ~1.5–3.5s by urgency; HT/FT ~2.0s.
- Settlement: `apply_bot_match_rewards` → `complete_run(..., last_minute=90)`.
- Interrupted bot runs: abandoned on boot (pre-057); competitive runs with `competitive_state` now silent-settle.

## Draw rate

- Regulation draws are uncommon but reachable; engine tests scan seeds for ET entry.
- With competitive flag ON, drawn 90' → ET 91–95 / 96–100 → pens if still level.

## Gate

Do not enable `competitive_match_enabled` in production until US1–US3 tests green and migration 109 verified.
