# Data Model: ElevenBoss Public Website

**Feature**: `008-public-website` | **Date**: 2026-07-11

No database. Entities are **content/config shapes** in the website repo (TypeScript + markdown). Nothing is persisted at request time.

## SiteConfig

Single source for marketing CTAs and structured copy. File: `src/config/site.ts`.

| Field | Type | Rules |
|-------|------|-------|
| `name` | `string` | `"ElevenBoss"` |
| `tagline` | `string` | Non-empty; shown in hero |
| `description` | `string` | Meta description / OG |
| `url` | `string` | Canonical production origin (set at launch) |
| `discord` | `DiscordLinks` | See below |
| `contact` | `ContactInfo` | Privacy/support contacts |
| `features` | `FeaturePillar[]` | Length ≥ 6 for v1 pillars |
| `homeTeasers` | `FeaturePillar[]` | Length 3; subset or shortened pillars |
| `getStarted` | `GetStartedStep[]` | Length 3–6; ordered |
| `nav` | `NavLink[]` | Header links |
| `footer` | `NavLink[]` | Must include Privacy + Terms |

### DiscordLinks

| Field | Type | Rules |
|-------|------|-------|
| `clientId` | `string` | Public Application Client ID; non-empty at ship |
| `permissions` | `string \| number` | Default `"8"` (Administrator); see [discord-invite.md](./contracts/discord-invite.md) |
| `scopes` | `string[]` | Must include `"bot"` and `"applications.commands"` |
| `supportInviteUrl` | `string` | Absolute `https://discord.gg/...` or `https://discord.com/invite/...` |
| `inviteUrl` (optional) | `string` | If set, overrides constructed OAuth URL |

### ContactInfo

| Field | Type | Rules |
|-------|------|-------|
| `supportLabel` | `string` | e.g. "Support Discord" |
| `privacyEmail` | `string` | Real email before production; no `[PRIVACY_EMAIL]` placeholder |
| `supportInviteUrl` | `string` | Same as `discord.supportInviteUrl` (or derived) |

### FeaturePillar

| Field | Type | Rules |
|-------|------|-------|
| `id` | `string` | Stable slug (`live-matches`, `squad`, …) |
| `title` | `string` | Non-empty |
| `description` | `string` | Plain-language benefit (≥1 sentence) |
| `icon` | `string` | Icon key or emoji sparingly |
| `mediaSrc` | `string?` | Path under `/media/` or external URL |

**Required pillar ids (v1)**: `live-matches`, `squad`, `evolution`, `leagues`, `economy`, `training-hub`.

### GetStartedStep

| Field | Type | Rules |
|-------|------|-------|
| `order` | `number` | 1-based contiguous |
| `title` | `string` | Short action title |
| `body` | `string` | Mentions real command/hub names when applicable |
| `href` | `string?` | Internal route or external invite |

### NavLink

| Field | Type | Rules |
|-------|------|-------|
| `label` | `string` | Visible text |
| `href` | `string` | Internal path or absolute URL |
| `external` | `boolean?` | `true` for Discord targets (`rel`/`target` handling) |

## LegalDocument

Markdown files under `content/`.

| Field | Source | Rules |
|-------|--------|-------|
| `slug` | filename | `privacy` \| `terms` |
| `title` | frontmatter or H1 | Required |
| `effectiveDate` | frontmatter | ISO or human date matching source drafts |
| `body` | markdown | Must cover topics listed in research R5 / spec FR-011 |
| `crossLinks` | markdown links | Privacy ↔ Terms use site routes `/privacy`, `/terms` |

**Validation (release)**: HTML output must not contain placeholder tokens:

- `[SUPPORT_SERVER_INVITE]`
- `[PRIVACY_EMAIL]`
- `[PLACEHOLDER]`

## MarketingPage (derived)

| Route | Primary entities |
|-------|------------------|
| `/` | SiteConfig (hero, teasers, getStarted), CTAs |
| `/features` | `features[]`, optional media, CTAs |
| `/privacy` | LegalDocument `privacy` |
| `/terms` | LegalDocument `terms` |
| `/invite` | DiscordLinks → redirect URL only |

## Relationships

```text
SiteConfig
  ├── features[] ──► FeaturePillar
  ├── homeTeasers[] ──► FeaturePillar
  ├── getStarted[] ──► GetStartedStep
  ├── discord ──► builds invite URL
  └── contact ──► mirrored into legal markdown at authoring time

LegalDocument (files) ── rendered by ──► /privacy, /terms
```

## State transitions

None at runtime. Content changes only via Git commit → Vercel deploy.

## Out of model (explicit non-entities)

- User accounts, sessions, cookies for auth
- Live club/match stats
- Bot token, Supabase keys, service roles
