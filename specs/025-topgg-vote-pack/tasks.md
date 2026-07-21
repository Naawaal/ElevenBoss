# Tasks: Top.gg Vote Gate for Free Store Pack

**Input**: Design documents from `/specs/025-topgg-vote-pack/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Required by plan — `tests/test_topgg_vote.py` (mocked httpx: voted, 404, 5xx, timeout, missing token). No Discord integration suite.

**Locked decisions** (research.md / plan.md):
- Top.gg **v1** `GET /projects/@me/votes/{discord_id}?source=discord` primary; v0 `/check` optional fallback only if v1 auth fails in staging
- Pack cooldown **22h → 12h** via `game_config.daily_pack_cooldown_hours`
- RPC `claim_daily_pack(p_club_id, p_cards, p_topgg_vote_at)` — drop 2-arg overload
- Column `players.last_consumed_topgg_vote_at` for vote replay prevention
- Fail closed on API errors; `topgg_vote_bypass_enabled=0` default
- No new slash command; `custom_id` stays `store_gacha_claim`
- Top.gg HTTP in `apps/discord_bot/core/topgg_vote.py` only — not `packages/`

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no incomplete dependencies)
- **[Story]**: US1–US4 maps to spec user stories
- Exact file paths required

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm touch list, env template, migration apply scaffold

- [x] T001 Grep `claim_daily_pack`, `last_claim_at`, `22 hours`, `store_gacha_claim`, `Claim Free Pack`; confirm single RPC caller is `apps/discord_bot/cogs/store_cog.py` and touch list matches `specs/025-topgg-vote-pack/plan.md`
- [x] T002 [P] Add `TOPGG_TOKEN` to `.env.example` per `plan.md` (comment: Top.gg Integrations & API token)
- [x] T003 [P] Create `scratch/apply_migration_069.py` from existing `scratch/apply_migration_068.py` pattern

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Migration 069, schema guards, RPC vote replay + 12h cooldown — **MUST complete before Store vote wiring**

**⚠️ CRITICAL**: Do not ship `store_cog` with `p_topgg_vote_at` until migration 069 is applied and `verify_required_schema.sql` passes

- [x] T004 Author `supabase/migrations/069_topgg_vote_pack.sql` per `contracts/claim-daily-pack-vote-rpc.md`: `last_consumed_topgg_vote_at` column; seed `daily_pack_cooldown_hours=12`, `topgg_vote_bypass_enabled=0`; `DROP` 2-arg `claim_daily_pack`; create 3-arg function with `VOTE_ALREADY_USED`, `VOTE_STALE`, `COOLDOWN:` exceptions; migration guard block
- [x] T005 Extend `supabase/scripts/verify_required_schema.sql`: `column:public.players.last_consumed_topgg_vote_at`; update `function:claim_daily_pack` guard to `public.claim_daily_pack(bigint,jsonb,timestamptz)`
- [x] T006 Apply migration via `scratch/apply_migration_069.py`; run `python scratch/verify_schema_full.py` or `psql $DATABASE_URL -f supabase/scripts/verify_required_schema.sql`
- [x] T007 [P] Create `tests/test_topgg_vote.py` with mocked `httpx` — cases: active vote (200), not voted (404), unavailable (500/timeout), empty token; **tests must fail** before T009

**Checkpoint**: Migration applied; schema verify green; topgg tests exist and fail (no module yet)

---

## Phase 3: User Story 1 — Vote Then Claim (Priority: P1) 🎯 MVP

**Goal**: Manager votes on Top.gg, clicks Store button, receives 5-card pack

**Independent Test**: No vote → prompt embed; after vote → pack claim embed; cooldown disables button

### Implementation for User Story 1

- [x] T008 [US1] Implement `apps/discord_bot/core/topgg_vote.py` — `VoteCheckResult`, `check_topgg_vote()` per `contracts/topgg-vote-api.md` (httpx async, 8s timeout, Bearer auth, no token logging)
- [x] T009 [US1] Make `tests/test_topgg_vote.py` pass (T007)
- [x] T010 [P] [US1] Add `topgg_vote_prompt_embed(vote_url)` in `apps/discord_bot/embeds/gacha_embeds.py` per `contracts/store-pack-copy.md`
- [x] T011 [US1] Wire `apps/discord_bot/cogs/store_cog.py` `gacha_claim_btn`: after defer, read `TOPGG_TOKEN`; call `check_topgg_vote`; on `not_voted` → prompt embed + re-enable view (no RPC); on `voted` → `generate_pack` → `claim_daily_pack` with `p_topgg_vote_at`; pass vote timestamp as ISO string in RPC payload key `p_topgg_vote_at`

**Checkpoint**: US1 demoable — vote gate works; pack grants only with active Top.gg vote

---

## Phase 4: User Story 2 — Double-Claim & Vote Replay Prevention (Priority: P1)

**Goal**: Same vote cycle cannot grant two packs; cooldown still enforced

**Independent Test**: Successful claim → second click within cooldown → cooldown embed; same `vote_at` replay → `VOTE_ALREADY_USED`

### Implementation for User Story 2

- [x] T012 [US2] Extend `apps/discord_bot/cogs/store_cog.py` exception handling: parse `VOTE_ALREADY_USED` → replay embed; parse `VOTE_STALE` → vote prompt embed (reuse T010)
- [x] T013 [P] [US2] Add `topgg_vote_replay_embed()` in `apps/discord_bot/embeds/gacha_embeds.py` per `contracts/store-pack-copy.md`
- [x] T014 [US2] Verify RPC `FOR UPDATE` + `last_consumed_topgg_vote_at` logic in migration 069 matches `data-model.md` state transitions (manual or dev DB spot-check after T011)

**Checkpoint**: US2 — no double pack from one vote; concurrent clicks safe via RPC lock

---

## Phase 5: User Story 3 — API Failure Graceful Degradation (Priority: P2)

**Goal**: Top.gg down / bad token → friendly message, no pack (fail closed)

**Independent Test**: Invalid token or mocked 503 → unavailable embed; no `claim_daily_pack` call

### Implementation for User Story 3

- [x] T015 [P] [US3] Add `topgg_vote_unavailable_embed()` in `apps/discord_bot/embeds/gacha_embeds.py` per `contracts/store-pack-copy.md`
- [x] T016 [US3] Wire `store_cog.py`: on `VoteCheckResult.status == "unavailable"` → unavailable embed + re-enable view; log warning without token
- [x] T017 [US3] Wire ops bypass in `store_cog.py`: when `get_game_config_int(db, "topgg_vote_bypass_enabled", 0) == 1`, skip API and pass `datetime.now(timezone.utc)` as `p_topgg_vote_at` (document in code comment — ops emergency only)

**Checkpoint**: US3 — fail closed by default; bypass works for ops

---

## Phase 6: User Story 4 — Store UX & Copy (Priority: P2)

**Goal**: `/store` embed and button reflect vote requirement and 12h cooldown

**Independent Test**: Open `/store` — copy mentions Top.gg; button label **Vote & Claim Free Pack**; cooldown timer uses 12h config

### Implementation for User Story 4

- [x] T018 [US4] Update Daily Gacha Pack field in `show_store()` — `apps/discord_bot/cogs/store_cog.py` per `contracts/store-pack-copy.md` (vote required, 12h cadence)
- [x] T019 [US4] Replace hardcoded 22h cooldown in `show_store()` with `get_game_config_int(db, "daily_pack_cooldown_hours", 12)` hours (match RPC)
- [x] T020 [US4] Change pack button label to `🗳️ Vote & Claim Free Pack` in `StoreHubView` (keep `custom_id="store_gacha_claim"`)
- [x] T021 [P] [US4] Update `gacha_cooldown_embed()` footer in `apps/discord_bot/embeds/gacha_embeds.py` — 12h + vote requirement per contract

**Checkpoint**: US4 — honest player-facing copy and timer

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Changelog, grep integrity, quickstart validation

- [x] T022 [P] Update `change_log.md` — free pack requires Top.gg vote; cooldown 12h; fail closed on verification outage
- [x] T023 Grep repo: zero `claim_daily_pack` 2-arg callers; zero `INTERVAL '22 hours'` in pack claim RPC path; zero new slash commands / hub buttons for this feature
- [x] T024 Run `specs/025-topgg-vote-pack/quickstart.md` — `pytest tests/test_topgg_vote.py -q`; manual vote → claim → cooldown smoke
- [x] T025 [P] Confirm `.specify/specs/v1.0.0/spec.md` US-02 already reflects vote gate (specify phase); patch if drift found

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Start immediately
- **Foundational (Phase 2)**: Depends on Setup — **BLOCKS** Store RPC wiring
- **US1 (Phase 3)**: Depends on Foundational (3-arg RPC must exist)
- **US2 (Phase 4)**: Depends on US1 (exception paths on live claim flow)
- **US3 (Phase 5)**: Depends on US1 (`topgg_vote.py` + store branches); embed T015 ∥ T016 after T015
- **US4 (Phase 6)**: Can start after US1; best after US3 for final copy pass
- **Polish (Phase 7)**: After US1–US4 complete

### User Story Dependencies

- **US1 (P1)**: After Foundational — **MVP**
- **US2 (P1)**: Builds on US1 claim handler
- **US3 (P2)**: Extends US1 vote check branches
- **US4 (P2)**: Mostly `show_store` / embeds; independent of US3

### Parallel Opportunities

- T002 ∥ T003 (env vs scratch script)
- T005 can draft in parallel with T004 once migration SQL is known
- T007 ∥ T004 (tests scaffold vs migration author — tests fail until T008)
- T010 ∥ T008 (embed vs client module)
- T013 ∥ T015 (replay vs unavailable embeds)
- T018–T021 largely parallel once US1 claim path exists
- T022 ∥ T025 (changelog vs SDD check)

---

## Implementation Strategy

### MVP First (Foundational + US1)

1. Phase 1 Setup  
2. Phase 2 Migration + schema verify + failing tests  
3. Phase 3 Top.gg client + Store vote gate + vote prompt  
4. **STOP and VALIDATE** — vote → claim works; no vote → prompt only  
5. Add US2–US4 + Polish before production deploy

### Deploy order (production-safe)

1. Apply migration **069** + verify schema  
2. Set `TOPGG_TOKEN` on Render  
3. Deploy bot with vote gate  
4. Do **not** deploy bot with 3-arg RPC call before migration is live

### Suggested release scope

**Foundational + US1 + US2 + US3 + US4** — ship as one release (vote gate is incomplete without replay + fail-closed UX).

---

## Notes

- Do not import `discord` or call Top.gg from `packages/`
- Do not register `StoreHubView` in `main.py` (ephemeral session view — unchanged)
- `generate_pack` / pack odds (024) — untouched
- Rollback: ops bypass `topgg_vote_bypass_enabled=1` for immediate relief; full revert needs coordinated bot + migration rollback
- Commit only when user requests
