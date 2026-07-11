# Quickstart: ElevenBoss Public Website

**Feature**: `008-public-website` | **Date**: 2026-07-11

Validation guide after the site repo is scaffolded. Spec/plan live in the bot monorepo; **runtime** is the separate `elevenboss-website` repo.

## Prerequisites

- Node 20+, pnpm 9+
- Discord Application **Client ID**
- Support server invite URL + privacy contact email
- Copies of `PRIVACY.md` / `TERMS.md` adapted into `content/` with placeholders replaced
- Vercel project linked to the website GitHub repo (for preview/production checks)

## Local setup

```bash
cd elevenboss-website
pnpm install
pnpm dev
```

Open `http://localhost:3000`.

```bash
pnpm build
# Expect static output (e.g. out/) with no build errors
```

## Config check

1. Open `src/config/site.ts`.
2. Confirm `clientId`, `supportInviteUrl`, `privacyEmail` are real values ([site-config.md](./contracts/site-config.md)).
3. Confirm scopes include `bot` and `applications.commands`.
4. Confirm six feature pillars and Get Started steps mention `/register`, `/squad`, `/development`, `/store` as planned.

## Manual scenarios

### 1. Landing invite (P1)

1. Open `/`.
2. **Expect**: ElevenBoss name, tagline, Invite + Support above the fold.
3. Click Invite → Discord OAuth shows bot install + command scope ([discord-invite.md](./contracts/discord-invite.md)).
4. Click Support → support Discord loads.
5. Resize to ~375px width → no horizontal scroll; CTAs tappable.

### 2. Features (P1)

1. Open `/features`.
2. **Expect**: Live Match Visuals, Squad Building, Player Evolution, League Competitions, Economy, Training Hub — each with description.
3. Optional media fails or missing → pillars still visible.
4. Footer/CTAs still offer Invite + Support.

### 3. Legal deep links (P1)

1. Cold-open `/privacy` and `/terms` (no home first).
2. **Expect**: Full bot-specific sections; effective date; contact block.
3. From home footer, open both links (≤2 clicks).
4. View page source / text → **no** `[SUPPORT_SERVER_INVITE]`, `[PRIVACY_EMAIL]`, or `[PLACEHOLDER]`.

### 4. Invite shortcut

1. Open `/invite`.
2. **Expect**: Redirect to the same OAuth URL as the Invite button ([routes.md](./contracts/routes.md)).

### 5. Get Started (P2)

1. On home, read Get Started steps.
2. **Expect**: Ordered actions; command/hub names match live bot.
3. Spot-check: a new manager can name the first in-bot action after invite (`/register`).

### 6. Performance / a11y gate

1. Production or `pnpm build` + static serve of home.
2. Lighthouse mobile: Performance ≥ 90, Accessibility ≥ 90 (or document exceptions).
3. Keyboard-only: tab to Invite and activate.

### 7. Secrets

1. Search website repo for `DISCORD_TOKEN`, `service_role`, `DATABASE_URL`.
2. **Expect**: zero matches in committed files and client bundles.

## Vercel preview

1. Push a branch → open Vercel preview URL.
2. Re-run scenarios 1–4 against preview.
3. After production domain: set Discord Developer Portal Privacy/Terms URLs to `https://{domain}/privacy` and `/terms`.

## Sync reminder

When bot data practices change, update ElevenBoss `PRIVACY.md` / `TERMS.md` **and** website `content/*.md` in the same release window.
