# Contract: Public Routes

**Feature**: `008-public-website`  
**Consumers**: Website visitors, Discord Developer Portal (deep links to Privacy/Terms)

## Routes

| Method | Path | Response | Notes |
|--------|------|----------|-------|
| GET | `/` | `200` HTML | Home / landing |
| GET | `/features` | `200` HTML | Full feature pillars |
| GET | `/privacy` | `200` HTML | Privacy Policy |
| GET | `/terms` | `200` HTML | Terms of Service |
| GET | `/invite` | `302` or `200`+redirect | Must land on Discord OAuth authorize URL |

All marketing routes are **static files** after export (no dynamic server). Trailing-slash behavior must match Next static export config consistently.

## Required HTML landmarks

| Route | Must include |
|-------|----------------|
| All | Header nav, footer with Privacy + Terms links |
| `/` | Brand name, tagline, Invite CTA, Support CTA, Get Started section or teaser |
| `/features` | Six pillars + Invite/Support CTAs |
| `/privacy` | Full policy body, effective date, contact |
| `/terms` | Full terms body, effective date, contact |
| `/invite` | No requirement to render marketing chrome if immediate redirect |

## Metadata

| Route | `title` pattern | `description` |
|-------|-----------------|---------------|
| `/` | `ElevenBoss — {tagline}` | From `SiteConfig.description` |
| `/features` | `Features · ElevenBoss` | Short feature summary |
| `/privacy` | `Privacy Policy · ElevenBoss` | Privacy one-liner |
| `/terms` | `Terms of Service · ElevenBoss` | Terms one-liner |

Open Graph image optional (`public/og-image.png`).

## Non-goals

- Authenticated routes
- API JSON endpoints under `/api/*` in v1
- Sitemap.xml / robots.txt optional but recommended (`robots.txt` allow all; `sitemap` listing the five routes)
