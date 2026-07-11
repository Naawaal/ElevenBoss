# Implementation Plan: ElevenBoss Public Website

**Branch**: `008-public-website` | **Date**: 2026-07-11 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/008-public-website/spec.md`

## Summary

Ship a **static marketing site** for ElevenBoss: home (hero + CTAs + get-started), features, privacy, and terms — with Discord invite (`bot` + `applications.commands`) and support-server CTAs. Host on **Vercel free tier** via GitHub; content in markdown + typed config (no CMS, no DB). Legal copy adapts existing `PRIVACY.md` / `TERMS.md`.

**Technical approach**: New GitHub repo `elevenboss-website` — Next.js App Router + `output: 'export'`, Tailwind, light shadcn/ui, pnpm, Framer Motion only if Lighthouse stays ≥90. Spec/plan artifacts remain in this bot monorepo under `specs/008-public-website/` for Speckit continuity; **no Discord bot, package, or migration changes**.

## Technical Context

**Language/Version**: TypeScript 5.x (strict), Node.js 20 LTS for local/CI builds

**Primary Dependencies**: Next.js 15 (App Router, static export), React 19, Tailwind CSS 4, shadcn/ui (Button/Card as needed), `gray-matter` + markdown renderer (or MDX) for legal pages, pnpm 9+

**Storage**: N/A (static files only). Content: `content/*.md` + `src/config/site.ts`. Public assets under `public/`

**Testing**: Manual QA via [quickstart.md](./quickstart.md); optional Playwright smoke later (not required for v1). `pnpm build` must succeed; Lighthouse mobile ≥90 Performance + Accessibility on home before launch

**Target Platform**: Static site on Vercel (global CDN); browsers: last two Chrome/Firefox/Safari/Edge; mobile-first

**Project Type**: Standalone marketing web app (separate Git repo from ElevenBoss bot monorepo)

**Performance Goals**: Lighthouse Performance & Accessibility ≥90 (home, mobile); invite CTA visible without waiting on heavy JS; legal pages readable with JS disabled where feasible

**Constraints**: Zero serverless invocations in v1 (pure static export); no bot token / Supabase keys in repo; Vercel free bandwidth; no CMS; English only; stats API deferred

**Scale/Scope**: 5 routes (`/`, `/features`, `/privacy`, `/terms`, `/invite`); ~8 UI components; 2 legal markdown docs; 1 site config module

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The ElevenBoss constitution governs the **Python Discord monorepo**. This feature’s **runtime** lives in a separate static site repo. Speckit docs stay here for governance.

| Gate | Status | Notes |
|------|--------|-------|
| I. Monorepo — no `discord` in `packages/` | PASS (N/A runtime) | No code added under `packages/` or `apps/discord_bot/`. Site is a separate repo |
| II. DB mutations via RPC | PASS (N/A) | No database; marketing pages are static |
| III. Typing / Pydantic at boundaries | PASS (adapted) | TypeScript strict + typed `SiteConfig`; no Python packages touched |
| IV. Slash + defer | PASS (N/A) | No Discord interactions |
| V. APScheduler | PASS (N/A) | No scheduled jobs |
| VI. Error handling / observability | PASS | Broken CTAs / placeholders fail release checklist; no secret leakage |
| VII. YAGNI | PASS | No CMS, auth, stats API, blog, or Edge functions in v1 |

**Post-Phase 1 re-check**: PASS — contracts are route/UI/content only; no bot schema or slash surfaces; separate-repo structure documented; secrets constrained in contracts.

## Project Structure

### Documentation (this feature)

```text
specs/008-public-website/
├── plan.md              # This file
├── research.md          # Phase 0 (blueprint + decisions)
├── data-model.md        # Phase 1 (content entities)
├── quickstart.md        # Phase 1 (validation guide)
├── contracts/
│   ├── routes.md
│   ├── site-config.md
│   ├── discord-invite.md
│   └── ui-pages.md
└── tasks.md             # /speckit.tasks (not this command)
```

### Source Code (new repo: `elevenboss-website`)

```text
elevenboss-website/
├── package.json                 # pnpm
├── pnpm-lock.yaml
├── next.config.ts               # output: 'export'; images unoptimized or static-compatible
├── tailwind.config.ts / CSS     # brand tokens
├── tsconfig.json
├── public/
│   ├── favicon.ico
│   ├── og-image.png             # optional social card
│   └── media/                   # optional small GIF/WebP demos
├── content/
│   ├── privacy.md               # adapted from ElevenBoss PRIVACY.md
│   └── terms.md                 # adapted from ElevenBoss TERMS.md
├── src/
│   ├── app/
│   │   ├── layout.tsx           # header/footer shell, fonts, metadata
│   │   ├── page.tsx             # home
│   │   ├── features/page.tsx
│   │   ├── privacy/page.tsx
│   │   ├── terms/page.tsx
│   │   └── invite/page.tsx      # client redirect or meta refresh to OAuth URL
│   ├── components/
│   │   ├── SiteHeader.tsx
│   │   ├── SiteFooter.tsx
│   │   ├── Hero.tsx
│   │   ├── CtaPair.tsx
│   │   ├── FeatureGrid.tsx
│   │   ├── FeatureCard.tsx
│   │   ├── GetStartedSteps.tsx
│   │   ├── LegalProse.tsx
│   │   └── MediaDemo.tsx       # optional
│   ├── config/
│   │   └── site.ts              # tagline, CTAs, features, get-started, contacts
│   └── lib/
│       ├── markdown.ts          # load/render legal MD
│       └── invite-url.ts        # build Discord OAuth URL from config
└── README.md                    # setup, env/public config, deploy
```

**Bot monorepo (this repo) — documentation only for this feature:**

```text
PRIVACY.md / TERMS.md            # Source drafts; keep in sync when practices change
specs/008-public-website/        # Speckit artifacts only
# NO changes to apps/, packages/, supabase/ for v1 website
```

**Structure Decision**: Separate GitHub repo for the site (user requirement + free Vercel project). Speckit plan/spec remain in ElevenBoss so product governance stays with the game. Do not place Next.js under `apps/` unless a future decision explicitly merges repos.

## Complexity Tracking

> No constitution violations requiring justification. Separate repo is a product/hosting choice, not a bypass of package boundaries.

| Note | Why | Simpler alternative rejected because |
|------|-----|--------------------------------------|
| Separate `elevenboss-website` repo | User asked for new Git + Vercel; keeps Python monorepo free of Node toolchain | `apps/website` in monorepo couples deploy/tooling and conflicts with “new repo” request |

## Implementation Notes (for `/speckit.tasks`)

1. **Scaffold** — `create-next-app` with App Router, TypeScript, Tailwind, pnpm; set `output: 'export'`; verify `pnpm build` emits `out/`.
2. **Brand tokens** — CSS variables from [research.md](./research.md) palette; Inter + Poppins via `next/font`.
3. **Config first** — `site.ts` holds client ID, permissions integer, support invite, privacy email, feature pillars, get-started steps ([site-config.md](./contracts/site-config.md)).
4. **Legal** — Copy `PRIVACY.md` / `TERMS.md` → `content/`; fix internal links to `/privacy` `/terms`; fill contact placeholders before production deploy.
5. **Invite** — Build URL per [discord-invite.md](./contracts/discord-invite.md); `/invite` redirects to same URL; default permissions `8` (Administrator) matching current ops invite for continuity.
6. **Pages** — Implement UI contracts in [ui-pages.md](./contracts/ui-pages.md) and routes in [routes.md](./contracts/routes.md).
7. **Motion** — Prefer CSS; add Framer Motion only if bundle still hits Lighthouse ≥90.
8. **Deploy** — GitHub → Vercel; custom domain optional; paste production Privacy/Terms URLs into Discord Developer Portal.
9. **Out of scope** — Edge/API routes, Supabase from site, auth, live stats, bot code changes, CMS.
