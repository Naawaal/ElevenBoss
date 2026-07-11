# Contract: UI Pages

**Feature**: `008-public-website`  
**Visual tokens**: [research.md](../research.md) palette + Inter/Poppins

## Global chrome

### SiteHeader

- Logo/wordmark → `/`
- Links: Features, Invite, Support (Support external)
- Mobile: accessible collapse or simple wrap; primary Invite still reachable
- Contrast: text on `--bg-deep` meets WCAG AA for normal text where feasible

### SiteFooter

- Links: Features, Privacy, Terms, Support, Invite
- Short copyright / product line
- Privacy + Terms always present (FR-004)

### CtaPair

- Primary: Invite (gold accent)
- Secondary: Support (outline / cyan)
- Both keyboard-focusable; visible focus ring

## Home (`/`)

| Section | Contract |
|---------|----------|
| Hero | Name `ElevenBoss`, tagline, CtaPair above the fold on 375px and 1280px widths |
| Value chips | Exactly 3 teasers linking to `/features` (or `#` anchors on features) |
| GetStartedSteps | Ordered list from config |
| Soft CTA | Repeat Invite or link to Features |

## Features (`/features`)

| Section | Contract |
|---------|----------|
| Intro | Title + one sentence |
| MediaDemo | Optional; if src missing/broken, pillars still render |
| FeatureGrid | All six pillars with title + description + icon |
| Closing | CtaPair + optional Get Started |

## Legal (`/privacy`, `/terms`)

| Rule | Detail |
|------|--------|
| Layout | Readable prose max-width (~65ch); dark theme still AA-ish contrast |
| Content | Rendered markdown from `content/*.md` |
| Cross-links | Privacy page links to `/terms` and vice versa |
| No chrome-only legal | Body must be in the document, not only a PDF download |

## Motion

- Optional section fade-in
- Honor `prefers-reduced-motion: reduce` (no required motion to use CTAs)
- Motion must not delay Invite interactivity beyond first paint of CTA markup

## Accessibility

- Semantic headings (single `h1` per page)
- Buttons/links have discernible names (“Invite ElevenBoss”, not “Click here”)
- Images/icons decorative ones `alt=""`; informative ones have alt text
