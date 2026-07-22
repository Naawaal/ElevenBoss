# Contract: Integrity Guards (HP-6)

**Parent**: [../spec.md](../spec.md) | US-42.5 / US-37

Must remain true after Wave 2:

1. Non-`lifecycle_v1` seasons still call `auto_sim_expired_fixtures` on hub open / hub refresh when a season is loaded.
2. Pause/resume paths in `build_hub_embed` (reachable guild → resume) are not removed or short-circuited by caching.
3. Season `status`, fixture `is_played`, and match locks are never served from process TTL as source of truth.
4. Coin/energy displays on profile remain from live player row + `sync_action_energy` (US-43 energy-line optimization allowed).

**Hard reject**: “Fast league hub” that skips settle or resume for latency.
