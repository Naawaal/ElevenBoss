# Research: Shelve PvP and Fix Surviving Automations

**Feature**: `056-shelve-pvp-automation`  
**Date**: 2026-08-08

## R1 — Rollback strategy (selective restore vs blanket revert)

**Decision**: Selective restoration to pre-PvP battle baseline `1737df6`, not `git revert` of the whole PvP range.

**Rationale**:
- `a564992` mixes Youth Academy V2 with early PvP — wholesale revert would destroy Academy.
- `818cca2` introduces the two automations that must survive.
- Commits after the PvP series (`52db6a3`, `4342889`, `a7266a4`, `99f899c`, etc.) may contain non-PvP match-lock / match_runs integrity work; restoring `battle_cog.py` by copying `1737df6` blindly would regress those fixes.
- Practical approach: delete dedicated PvP modules; for shared files, remove PvP hunks by diffing against `1737df6` **and** against current HEAD, keeping Academy + later integrity/automation lines.

**Alternatives considered**:
- `git revert` range `a564992^..954e9ee` — rejected (destroys Academy; conflicts with later commits).
- Soft-disable via `battle_pvp_enabled=false` only — rejected (spec requires complete erasure of active PvP surfaces).

### Commit map (action)

| Commit | Action |
|--------|--------|
| `1737df6` | Pre-PvP battle/matchmaking reference |
| `a564992` | Selective: keep Academy, remove PvP |
| `1833623` … `954e9ee` | Remove PvP artifacts from tree |
| `818cca2` | Keep automations; do not wholesale revert |
| `8669230` | Selective: keep changelog service; remove commit-key / PvP-adjacent battle material |
| Later non-PvP commits | Keep match integrity / unrelated fixes |

## R2 — Database: delete 098–106 files + forward cleanup 108

**Decision**: Remove migration files `098`–`106` from the repo; keep `095`–`097` and `107`; add **`108_shelve_pvp_and_version_changelog.sql`** that idempotently drops all PvP objects and restores shared CHECKs/functions to post-097 / pre-098 shapes; also redefines changelog RPCs for version-only keys.

**Rationale**: Applied remotes already ran 098–106; deleting files alone leaves orphan schema. Forward-only cleanup matches Section 8 (never rewrite applied migrations). Fresh installs never create PvP objects (files gone); `108` uses `DROP IF EXISTS` so it is safe either way.

**Alternatives considered**:
- Keep 098–106 as historical no-ops — rejected (spec wants artifacts removed; operators still need 108 for applied DBs).
- `supabase db reset` only — rejected (production cannot reset).

### Objects 108 must drop / restore (non-exhaustive; derive full list by grepping 098–106)

- Tables: `pvp_matchmaking_queue`, `manager_rivalries`, `pvp_blocks`, `pvp_ghost_snapshots`, `pvp_ghost_encounters`, related encounter/backfill tables
- Columns/flags: PvP prefs/badges on `players`; PvP columns on `match_history`; `game_config` keys `battle_pvp_enabled`, `pvp_rewards_enabled`, `pvp_rivalries_enabled`, energy/search tunables
- CHECK values: `pvp` / `practice` on `match_runs` / `match_locks` / `match_history` — restore to 097-era allowed sets
- RPCs: `join_pvp_queue`, `try_match_pvp_queue`, `finalize_pvp_match`, `complete_pvp_run`, ghost/backfill/rivalry helpers, etc.
- Indexes + RLS policies for those tables
- Restore `acquire_match_lock` (and any shared functions rewritten by 098+) from **097 definitions**, not hand approximations

## R3 — Changelog: version-only dedupe

**Decision**: Change the claim identity from `"{version}:{commit[:7]}"` to **`"{version}"` only**. Compare latest parsed `## [X.Y.Z]` against the recorded posted/claimed version. Do not use commit SHA, mtime, deploy ID, or whole-file hash in the decision.

**Rationale**: Current bug is confirmed in `deployment_changelog.py` (`deployment_key = f"{entry.version}:{commit[:7]}"`). Same version + new commit → new key → repost. Version-only key fixes SC-004/SC-005/SC-006 with minimal RPC surface change.

**Implementation notes**:
- Keep RPC names `claim_deployment_changelog` / `complete_deployment_changelog` (migration 107) but treat `p_deployment_key` as the **version string**.
- `complete_deployment_changelog` may still store optional commit metadata for ops, but equality / already_posted checks MUST ignore commit.
- On failed Discord send after claim: do not call complete; allow 10-minute claim TTL (already in 107) to expire so another instance/restart can retry — satisfies FR-010.
- Channel resolution + embed builder unchanged.

**Alternatives considered**:
- Separate `last_changelog_version` key — unnecessary if `deployment_key` becomes the version.
- File hash of `change_log.md` — rejected (body edits under same header would repost).

## R4 — Vote reminder hardening

**Decision**: Keep Feature 055 stack; tighten three behaviors only:

1. **Window authority**: `reminder_window_key` is the sole completion identity; mark window handled on successful DM **or** Forbidden→fallback path so concurrent instances cannot complete twice.
2. **Cooldown**: Prefer Top.gg `next_vote_at` when present; else `last_vote_at + 12h` (existing upsert shape — verify all call sites).
3. **Fallback**: `Forbidden` → `dm_status='forbidden'`, `fallback_pending=true`, `reminder_sent_at` set (or equivalent “handled” stamp) so the job does not DM again; Store shows once via `maybe_send_pending_vote_notice` and clears.

**Rationale**: Spec accepts 30-minute cadence. Base implementation already claims with `SKIP LOCKED` and 15-minute stale reclaim; gaps are ensuring Forbidden counts as terminal for the window and that schedule sources prefer Top.gg’s next time.

**Alternatives considered**:
- Per-minute reminder polling — rejected (spam risk; YAGNI).
- Rebuild reminder table — rejected (107 schema sufficient).

## R5 — `/battle` restore approach

**Decision**: Restore Bot Battle + Friendly UX from pre-PvP baseline; delete Find Opponent / Ranked / Practice / queue / rivalry entry points and all `pvp_*` imports from `battle_cog.py`. Prefer surgical removal of PvP branches over wholesale file checkout when later non-PvP commits touched the same file.

**Rationale**: Spec FR-002 / SC-001–002. Baseline `1737df6` is the behavioral reference for modes; HEAD may include match-run locking improvements that must remain.

## R6 — Docs / SDD / grep gate

**Decision**: Delete `specs/053-*` and `specs/054-*`. Strip PvP mentions from `.specify/specs/v1.0.0/spec.md` + `plan.md`, `change_log.md` (as product copy for this release), and `verify_required_schema.sql`. Final gate: codebase search for `pvp`, `rivalry`, `ghost manager`, `battle_pvp_enabled`, `join_pvp_queue`, `finalize_pvp_match`, etc. returns zero product hits (history excluded). Note: benign uses of the English word “practice” outside PvP mode must not force false positives — gate on PvP-specific tokens first.

**Rationale**: Spec FR-004/015, SC-003/009.

## Resolved clarifications

No open NEEDS CLARIFICATION items remain from Technical Context. Rollback boundary, migration strategy, changelog key, and reminder hardening are all decided above.
