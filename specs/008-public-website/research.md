# Research: ElevenBoss Public Website

**Feature**: [008-public-website](./spec.md)  
**Plan**: [plan.md](./plan.md)  
**Updated**: 2026-07-11 (Phase 0 — all open decisions resolved)

---

## R1 — Hosting & framework

**Decision**: Next.js 15 App Router with `output: 'export'` (fully static), deployed to Vercel free via GitHub; package manager **pnpm**.

**Rationale**: User required Vercel-friendly static hosting, zero/near-zero serverless use, and easy Git deploys. Static export stays within free-tier function limits (0 invocations). Next.js is the default Vercel path; App Router is current.

**Alternatives considered**:
- Pages Router — works, but App Router is the maintained default for new apps
- Astro / plain HTML — lighter, but weaker alignment with user’s Next.js preference and shadcn ecosystem
- SSR / Edge for stats — rejected for v1 (YAGNI, function quota)

---

## R2 — Repository layout

**Decision**: New GitHub repository `elevenboss-website`. Speckit docs remain in ElevenBoss under `specs/008-public-website/`.

**Rationale**: Spec assumption and user workflow (“new Git repository, connect Vercel”). Avoids Node tooling inside the Python monorepo.

**Alternatives considered**:
- `apps/website` in ElevenBoss monorepo — simpler content sync, but mixes runtimes and was explicitly not requested for v1
- Submodule linking legal markdown — overkill; copy + sync note is enough

---

## R3 — Styling & components

**Decision**: Tailwind CSS + CSS variables for brand tokens; shadcn/ui sparingly (Button, Card, Separator); Inter (body) + Poppins (headings) via `next/font`.

**Rationale**: Matches design direction (dark football theme, mobile-first). shadcn avoids inventing primitives; fonts load without layout shift.

**Alternatives considered**:
- CSS Modules only — slower iteration
- Heavy component library (MUI) — wrong aesthetic and weight
- Emoji-heavy UI — rejected by brand constraints

### Palette (locked for implementation)

| Token | Hex | Role |
|-------|-----|------|
| `--bg-deep` | `#0B1220` | Page background |
| `--bg-panel` | `#121A2B` | Sections / cards |
| `--pitch-green` | `#0F3D2E` | Gradient depth |
| `--accent-gold` | `#E8C547` | Primary CTA |
| `--accent-cyan` | `#2EE6D6` | Links / secondary |
| `--text` | `#E8EEF7` | Body |
| `--text-muted` | `#9AA8BC` | Secondary |
| `--danger` | `#F07178` | Errors only |

---

## R4 — Motion

**Decision**: CSS fade/slide reveals first; optional Framer Motion only if Lighthouse Performance stays ≥90 on mobile home.

**Rationale**: Spec requires subtle motion without blocking CTAs; reduced-motion respected via `prefers-reduced-motion`.

**Alternatives considered**:
- Framer Motion everywhere — risk bundle/perf
- No motion — acceptable fallback if perf regresses

---

## R5 — Content & legal

**Decision**: Legal bodies live as `content/privacy.md` and `content/terms.md`, adapted from bot-repo `PRIVACY.md` / `TERMS.md` (effective 11 July 2026). Marketing copy and CTAs in `src/config/site.ts`.

**Rationale**: No CMS (FR-008); single typed config for maintainers; legal already drafted for Discord verification.

**Alternatives considered**:
- Fetch legal from GitHub raw at build time — fragile coupling
- Hardcoded JSX legal pages — harder to update
- Headless CMS — out of scope / cost

---

## R6 — Discord invite permissions

**Decision**: Invite URL scopes fixed to `bot applications.commands`. Permissions integer is **configurable** in `site.ts`, **default `8` (Administrator)** to match the invite pattern already documented in `scripts/vps-ops.md`.

**Rationale**: Continuity with existing invite links and admin-configured leagues. Least-privilege audit is a **post-v1** follow-up (document target bitmask after reviewing real guild channel/role needs).

**Alternatives considered**:
- Ship a guessed minimal bitmask now — risk broken league setup for new servers
- Omit permissions param — Discord may under-grant; worse UX

---

## R7 — Features page vs home

**Decision**: **Both** — home shows 3 value chips + Get Started teaser linking to `/features`; `/features` has the full six pillars + optional media.

**Rationale**: Spec FR-002 allows dedicated page and/or home section; teaser converts, full page educates without drowning the hero.

**Alternatives considered**:
- Home-only long scroll — heavy first paint
- Features-only (no home teaser) — weaker conversion education

---

## R8 — Demo media hosting

**Decision**: Prefer small WebP/GIF under `public/media/` if total demo assets stay under ~2 MB. If larger, embed external (YouTube/Loom) and do not host large video on Vercel.

**Rationale**: Free-tier bandwidth; static export has no image optimizer CDN features the same way as non-export Next.

**Alternatives considered**:
- Always external embed — extra third-party dependency for a tiny GIF
- Large MP4 on Vercel — burns bandwidth

---

## R9 — Live stats / Edge API

**Decision**: **Out of scope for v1.** No Supabase client, no Edge routes.

**Rationale**: Spec P3 / FR-016; avoids secrets and serverless quota.

**Alternatives considered**:
- Public read-only RPC later — possible after a dedicated public contract exists

---

## R10 — Get Started steps (content lock)

**Decision**: Ordered steps in `site.ts` (3–6 items), aligned to live bot:

1. Invite ElevenBoss (`/invite` or CTA)
2. `/register` — create club and starting squad
3. `/squad` — set your XI
4. Play a match (bot / friendly / league as available)
5. `/development` — drills, fusion, skills
6. `/store` — daily login and energy (optional 6th)

**Rationale**: Matches current hubs; avoids obsolete command names (SC-008 / FR-012).

**Alternatives considered**:
- Vague “join and play” copy — fails independent test
- Linking only Top.gg — not the product surface

---

## Wireframes (reference)

See prior blueprint sections retained below for implementers.

### Landing `/`

```text
[Logo]  Features · Invite · Support
ELEVENBOSS + tagline + [Invite] [Support]
3 value chips → link Features
How to Get Started (steps)
CTA strip + Footer (Privacy · Terms · Support · Invite)
```

### Features `/features`

```text
Title + optional MediaDemo
FeatureGrid (6 pillars)
Get Started + CTAs + Footer
```

---

## Deployment checklist (absorbed into plan)

### Pre-code
- [x] Spec approved path exists
- [x] Plan + research decisions locked
- [ ] Discord Application Client ID confirmed by maintainer
- [ ] Support invite + privacy email confirmed

### Pre-launch
- [ ] `pnpm build` → static `out/`
- [ ] All routes work on Vercel preview
- [ ] No `[PLACEHOLDER]` / `[SUPPORT_SERVER_INVITE]` / `[PRIVACY_EMAIL]` in HTML
- [ ] Invite OAuth scopes include `bot` + `applications.commands`
- [ ] Lighthouse mobile Performance & Accessibility ≥ 90 (home)
- [ ] Secrets scan clean
- [ ] Discord Developer Portal Privacy/Terms URLs set

### Post-launch
- [ ] Announce URL in support server
- [ ] Sync legal when bot data practices change
