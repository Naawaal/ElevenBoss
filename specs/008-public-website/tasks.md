# Tasks: ElevenBoss Public Website

**Input**: Design documents from `/specs/008-public-website/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Manual only — follow `quickstart.md` and Lighthouse gates. No automated test suite required for v1 (Playwright optional later).

**Organization**: Tasks grouped by user story (US1–US6) for incremental delivery.

**Implementation root**: Separate GitHub repo `elevenboss-website/` (paths below are relative to that repo). Speckit docs stay in ElevenBoss `specs/008-public-website/`.

**Locked decisions** (from research.md R1–R10):
- Next.js 15 App Router + `output: 'export'` → Vercel; pnpm
- Separate repo `elevenboss-website` (not `apps/website`)
- Tailwind + brand CSS variables; Inter + Poppins; shadcn sparingly
- Invite scopes `bot` + `applications.commands`; permissions default `8`
- Home teasers (3) + full `/features` (6 pillars)
- Legal from ElevenBoss `PRIVACY.md` / `TERMS.md` → `content/`
- Live stats / Edge / Supabase from site: out of v1
- Motion: CSS first; Framer Motion only if Lighthouse stays ≥90

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1 / US2 / US3 / US4 / US5 / US6
- Include exact file paths in descriptions

## Path Conventions

- Website repo: `elevenboss-website/` (create if missing)
- App routes: `src/app/`
- Components: `src/components/`
- Config/lib: `src/config/`, `src/lib/`
- Content: `content/`
- Public assets: `public/`
- Feature docs (this monorepo): `specs/008-public-website/`
- Legal sources (this monorepo): `PRIVACY.md`, `TERMS.md`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the website repository and scaffold the Next.js static app

- [x] T001 Create GitHub repository `elevenboss-website` (empty or README-only) and clone it locally as the implementation root
- [x] T002 Scaffold Next.js 15 App Router + TypeScript + Tailwind with pnpm in `elevenboss-website/` (`create-next-app` or equivalent); commit `package.json` and `pnpm-lock.yaml`
- [x] T003 [P] Set `output: 'export'` (and static-export-compatible image settings) in `elevenboss-website/next.config.ts`; verify `pnpm build` emits static `out/`
- [x] T004 [P] Add project README with setup, build, deploy, and config notes in `elevenboss-website/README.md`
- [x] T005 [P] Add `.gitignore` for Node/Next (`.env*`, `node_modules`, `out`, `.next`) in `elevenboss-website/.gitignore`; ensure no bot token patterns are committed

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Brand shell, typed site config, invite URL helper, and shared chrome that all stories reuse

**⚠️ CRITICAL**: No user-story page polish until config, layout chrome, and invite helper exist

- [x] T006 Define typed `SiteConfig` and export defaults (name, tagline, description, discord links with scopes/`permissions: 8`, nav, footer, empty-safe placeholders flagged for launch) in `elevenboss-website/src/config/site.ts` per `specs/008-public-website/contracts/site-config.md` and `data-model.md`
- [x] T007 [P] Implement pure `buildInviteUrl` (and optional override via `discord.inviteUrl`) in `elevenboss-website/src/lib/invite-url.ts` per `specs/008-public-website/contracts/discord-invite.md`
- [x] T008 [P] Add brand CSS variables (`--bg-deep`, `--accent-gold`, etc.) and Inter + Poppins via `next/font` in `elevenboss-website/src/app/globals.css` and `elevenboss-website/src/app/layout.tsx` per `research.md` palette
- [x] T009 Implement `SiteHeader` (logo → `/`, Features, Invite, Support) in `elevenboss-website/src/components/SiteHeader.tsx` per `contracts/ui-pages.md`
- [x] T010 [P] Implement `SiteFooter` (Features, Privacy, Terms, Support, Invite) in `elevenboss-website/src/components/SiteFooter.tsx` per `contracts/ui-pages.md`
- [x] T011 [P] Implement reusable `CtaPair` (Invite + Support) in `elevenboss-website/src/components/CtaPair.tsx` using `buildInviteUrl` / `supportInviteUrl`
- [x] T012 Wire `SiteHeader` + `SiteFooter` into root layout metadata shell in `elevenboss-website/src/app/layout.tsx`; add favicon under `elevenboss-website/public/favicon.ico`
- [x] T013 Confirm `pnpm build` still succeeds with empty/placeholder page routes and no secrets in the client bundle

**Checkpoint**: Layout renders with header/footer; invite helper builds a valid OAuth URL shape; static export works

---

## Phase 3: User Story 1 — Discover and Invite the Bot (Priority: P1) 🎯 MVP

**Goal**: Visitor lands on home, understands ElevenBoss, and can Invite or Join Support in one or two clicks; `/invite` shortcuts to OAuth

**Independent Test**: Open `/` on desktop and ~375px; see name, tagline, Invite + Support; Invite opens Discord authorize with `bot` + `applications.commands`; Support opens community invite; `/invite` redirects to same OAuth URL

### Implementation for User Story 1

- [x] T014 [US1] Implement `Hero` (brand name, tagline, `CtaPair`) in `elevenboss-website/src/components/Hero.tsx`
- [x] T015 [US1] Build home page above-the-fold hero (+ minimal value strip placeholder OK) in `elevenboss-website/src/app/page.tsx`
- [x] T016 [US1] Implement `/invite` redirect to Discord OAuth URL in `elevenboss-website/src/app/invite/page.tsx` (meta refresh and/or client redirect compatible with static export) per `contracts/routes.md`
- [x] T017 [US1] Fill real `discord.clientId` and `discord.supportInviteUrl` in `elevenboss-website/src/config/site.ts` (or documented public env mapped at build time); reject shipping with empty `client_id=`
- [x] T018 [US1] Manually verify US1 against `specs/008-public-website/quickstart.md` scenarios 1 and 4

**Checkpoint**: MVP invite conversion path works locally via `pnpm dev` / static preview

---

## Phase 4: User Story 2 — Learn What the Game Offers (Priority: P1)

**Goal**: Features experience explains six game pillars with icons/descriptions and optional media; CTAs remain available

**Independent Test**: Open `/features`; see Live Match Visuals, Squad Building, Player Evolution, League Competitions, Economy, Training Hub with benefit copy; broken media does not hide pillars; Invite/Support still reachable

### Implementation for User Story 2

- [x] T019 [P] [US2] Populate six `features` pillars (+ three `homeTeasers`) in `elevenboss-website/src/config/site.ts` per required ids in `data-model.md`
- [x] T020 [P] [US2] Implement `FeatureCard` in `elevenboss-website/src/components/FeatureCard.tsx`
- [x] T021 [US2] Implement `FeatureGrid` in `elevenboss-website/src/components/FeatureGrid.tsx`
- [x] T022 [US2] Build `/features` page (intro, grid, closing `CtaPair`) in `elevenboss-website/src/app/features/page.tsx` per `contracts/ui-pages.md`
- [x] T023 [P] [US2] Add optional `MediaDemo` and small asset under `elevenboss-website/src/components/MediaDemo.tsx` + `elevenboss-website/public/media/` (skip large video; WebP/GIF &lt; ~2MB or external embed)
- [x] T024 [US2] Wire home value chips to `homeTeasers` linking to `/features` in `elevenboss-website/src/app/page.tsx`
- [x] T025 [US2] Manually verify US2 against `quickstart.md` scenario 2

**Checkpoint**: Features page and home teasers educate without blocking invite CTAs

---

## Phase 5: User Story 3 — Privacy Policy and Terms (Priority: P1)

**Goal**: Dedicated `/privacy` and `/terms` with bot-specific legal copy; footer links work from every page

**Independent Test**: Cold-open `/privacy` and `/terms`; required sections present; footer links resolve; no `[SUPPORT_SERVER_INVITE]`, `[PRIVACY_EMAIL]`, or `[PLACEHOLDER]` strings

### Implementation for User Story 3

- [x] T026 [P] [US3] Adapt ElevenBoss `PRIVACY.md` into `elevenboss-website/content/privacy.md` (route links `/privacy`↔`/terms`; fill support invite + privacy email)
- [x] T027 [P] [US3] Adapt ElevenBoss `TERMS.md` into `elevenboss-website/content/terms.md` (same contact/link rules)
- [x] T028 [US3] Implement markdown loader/renderer in `elevenboss-website/src/lib/markdown.ts`
- [x] T029 [P] [US3] Implement `LegalProse` in `elevenboss-website/src/components/LegalProse.tsx`
- [x] T030 [US3] Build `/privacy` page in `elevenboss-website/src/app/privacy/page.tsx`
- [x] T031 [P] [US3] Build `/terms` page in `elevenboss-website/src/app/terms/page.tsx`
- [x] T032 [US3] Grep built HTML / content for placeholder tokens; fix until clean; verify footer Privacy/Terms on all routes
- [x] T033 [US3] Manually verify US3 against `quickstart.md` scenario 3

**Checkpoint**: Discord verification reviewers can deep-link legal pages

---

## Phase 6: User Story 4 — How to Get Started (Priority: P2)

**Goal**: Ordered 3–6 onboarding steps using real command/hub names so new managers are not stuck after invite

**Independent Test**: Read Get Started on home (and optionally features); steps mention `/register`, `/squad`, match play, `/development`, `/store` as planned; a new manager can name the first in-bot action

### Implementation for User Story 4

- [x] T034 [US4] Add ordered `getStarted` steps (3–6) to `elevenboss-website/src/config/site.ts` per research R10 / `contracts/site-config.md`
- [x] T035 [US4] Implement `GetStartedSteps` in `elevenboss-website/src/components/GetStartedSteps.tsx`
- [x] T036 [US4] Mount Get Started on home in `elevenboss-website/src/app/page.tsx` and optionally on features in `elevenboss-website/src/app/features/page.tsx`
- [x] T037 [US4] Manually verify US4 against `quickstart.md` scenario 5

**Checkpoint**: Onboarding path is visible and accurate to live bot hubs

---

## Phase 7: User Story 5 — Contact / Support (Priority: P2)

**Goal**: Visitors find support Discord and privacy contact path consistent with the Privacy Policy

**Independent Test**: From footer/contact section, open support invite; privacy contact instructions match `/privacy` contact block

### Implementation for User Story 5

- [x] T038 [US5] Add a Contact/Support section (home footer strip or dedicated block) in `elevenboss-website/src/app/page.tsx` and/or `elevenboss-website/src/components/SiteFooter.tsx` using `site.contact`
- [x] T039 [US5] Align `contact.privacyEmail` + support invite strings across `src/config/site.ts`, `content/privacy.md`, and `content/terms.md`
- [x] T040 [US5] Spot-check Support CTA and privacy contact copy for consistency (quickstart Contact expectations)

**Checkpoint**: Support and privacy request paths are obvious and consistent

---

## Phase 8: User Story 6 — Optional Live Stats Deferred (Priority: P3)

**Goal**: Confirm v1 ships **without** live stats widgets or Edge/Supabase calls; no broken empty stats UI

**Independent Test**: Browse home/features — no stats widget, no `/api` stats fetch, no Supabase client in dependencies

### Implementation for User Story 6

- [x] T041 [US6] Grep `elevenboss-website/` for `supabase`, `@supabase`, stats widgets, and `app/api/`; remove any accidental v1 stats/Edge code
- [x] T042 [US6] Document in `elevenboss-website/README.md` that live stats are deferred (optional future public feed only)

**Checkpoint**: YAGNI held — site remains static with zero function invocations for stats

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Launch readiness across all stories

- [x] T043 [P] Add `robots.txt` and optional `sitemap.xml` (or App Router equivalents under `src/app`) listing `/`, `/features`, `/privacy`, `/terms`, `/invite`
- [x] T044 [P] Add optional `public/og-image.png` and Open Graph metadata in `src/app/layout.tsx` / page metadata
- [x] T045 Add subtle CSS motion with `prefers-reduced-motion` respect; only add Framer Motion if mobile Lighthouse Performance remains ≥90
- [ ] T046 Connect GitHub repo to Vercel; confirm preview deploy serves all routes from static export
- [ ] T047 Run Lighthouse mobile on production/preview home — Performance ≥90 and Accessibility ≥90 (or document exceptions) per `quickstart.md` scenario 6
- [x] T048 [P] Secrets scan (`DISCORD_TOKEN`, `service_role`, `DATABASE_URL`) per `quickstart.md` scenario 7
- [ ] T049 Fill Discord Developer Portal Privacy/Terms URLs with production `/privacy` and `/terms`
- [ ] T050 Run full `specs/008-public-website/quickstart.md` checklist; announce site URL in support server when green
- [x] T051 [P] Note sync reminder: when bot legal practices change, update ElevenBoss `PRIVACY.md`/`TERMS.md` and website `content/*.md` together

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — **BLOCKS** all user stories
- **US1 (Phase 3)**: After Foundational — MVP
- **US2 (Phase 4)**: After Foundational (can parallel with US1/US3 after chrome exists; home teasers integrate with US1 page)
- **US3 (Phase 5)**: After Foundational — required before Discord verification / public trust launch
- **US4 (Phase 6)**: After Foundational; best after US1 home exists
- **US5 (Phase 7)**: After US3 contacts exist in legal markdown (align strings)
- **US6 (Phase 8)**: Anytime after Foundational; typically with Polish
- **Polish (Phase 9)**: After desired stories (recommend US1–US5 before production)

### User Story Dependencies

- **US1 (P1)**: No dependency on other stories — MVP
- **US2 (P1)**: Independent page; home teasers touch `page.tsx` shared with US1
- **US3 (P1)**: Independent routes; footer links already in foundational chrome
- **US4 (P2)**: Extends home/features; depends on US1 page shell ideally
- **US5 (P2)**: Aligns with US3 contact fields
- **US6 (P3)**: Verification-only; no feature build

### Parallel Opportunities

- T003–T005 after scaffold
- T007–T008, T010–T011 after `site.ts` types exist
- T019–T020, T023 within US2
- T026–T027, T029, T031 within US3
- T043–T044, T048, T051 in Polish

---

## Parallel Example: User Story 2

```bash
# After foundational chrome exists:
Task: "Populate six features + homeTeasers in src/config/site.ts"
Task: "Implement FeatureCard in src/components/FeatureCard.tsx"
Task: "Add MediaDemo + public/media asset (optional)"
# Then sequentially:
Task: "FeatureGrid → features/page.tsx → home teasers → quickstart §2"
```

## Parallel Example: User Story 3

```bash
Task: "Adapt PRIVACY.md → content/privacy.md"
Task: "Adapt TERMS.md → content/terms.md"
# Then:
Task: "markdown.ts → LegalProse → privacy/page.tsx + terms/page.tsx → placeholder grep"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup  
2. Complete Phase 2: Foundational  
3. Complete Phase 3: US1  
4. **STOP and VALIDATE**: Invite + Support on home + `/invite`  
5. Preview deploy if desired  

### Recommended public launch slice

1. MVP (US1)  
2. US2 Features + US3 Legal (Discord portal + trust)  
3. US4 Get Started + US5 Contact  
4. US6 verification + Phase 9 Polish (Lighthouse, Vercel, portal URLs)  

### Incremental Delivery

1. Setup + Foundational → shell ready  
2. US1 → invite conversion  
3. US2 → education  
4. US3 → compliance URLs  
5. US4/US5 → onboarding + support clarity  
6. Polish → production  

---

## Notes

- [P] = different files, no incomplete-task dependency
- Do **not** modify ElevenBoss `apps/`, `packages/`, or `supabase/` for this feature
- Replace placeholder Client ID / support invite / email before production
- Prefer CSS motion; treat Framer Motion as optional and perf-gated
- Commit in the website repo after each phase or logical group
- Stop at any checkpoint to validate the story independently
