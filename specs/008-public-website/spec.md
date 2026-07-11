# Feature Specification: ElevenBoss Public Website

**Feature Branch**: `008-public-website`

**Created**: 2026-07-11

**Status**: Draft

**Input**: User description: "Create a stunning, responsive public website for ElevenBoss as the bot’s public face — landing, features, privacy, and terms — hosted on a free static-friendly platform, easy to maintain, with invite/support CTAs; design and architecture plan required before any code."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Discover and Invite the Bot (Priority: P1)

As a Discord server owner or football-game fan discovering ElevenBoss, I open the public website, immediately understand what the bot is, and can invite it to my server or join the support community in one or two clicks.

**Why this priority**: Invite and community join are the primary conversion goals of a bot marketing site; without them the site does not fulfill its purpose.

**Independent Test**: Open the home page on desktop and mobile; confirm hero shows bot name, tagline, and working Invite + Support CTAs; complete the invite flow to Discord’s authorization screen.

**Acceptance Scenarios**:

1. **Given** a visitor lands on the home page, **When** the page loads, **Then** they see the ElevenBoss name, a short tagline, and two clear primary actions: Invite the Bot and Join Support Server.
2. **Given** the visitor taps Invite, **When** Discord’s authorization page opens, **Then** the invite requests bot install with application commands (slash commands) so the bot is usable after install.
3. **Given** the visitor taps Join Support, **When** the link opens, **Then** they reach the official ElevenBoss support/community Discord invite.
4. **Given** a visitor on a phone-width screen, **When** they view the home page, **Then** hero content and CTAs remain readable and tappable without horizontal scrolling.

---

### User Story 2 - Learn What the Game Offers (Priority: P1)

As a curious manager evaluating whether to try ElevenBoss, I browse a Features experience that explains the main game pillars with short descriptions and visuals, so I can decide to invite without joining Discord first.

**Why this priority**: Feature clarity drives invite conversion and reduces “what does this bot do?” support questions.

**Independent Test**: Open Features from the nav or home; confirm each listed game pillar has a title, short description, and supporting visual or icon; verify the page works on mobile.

**Acceptance Scenarios**:

1. **Given** a visitor opens Features, **When** the page loads, **Then** they see distinct sections (or cards) for at least: Live Match Visuals, Squad Building, Player Evolution, League Competitions, Economy, and Training / Development Hub.
2. **Given** a feature section, **When** the visitor reads it, **Then** they understand the benefit in plain language (one short paragraph or equivalent), not only a label.
3. **Given** optional media is provided (demo GIF or embed), **When** the visitor views Features, **Then** at least one visual demo of match or hub gameplay is present without blocking the rest of the page if media fails to load.
4. **Given** a visitor finishes Features, **When** they look for next steps, **Then** Invite and Support CTAs remain available (page or sticky/footer).

---

### User Story 3 - Read Privacy Policy and Terms (Priority: P1)

As a Discord server admin or privacy-conscious user (including Discord app verification reviewers), I open dedicated Privacy Policy and Terms pages with bot-specific, plain-language legal content, and can find those links from every page footer.

**Why this priority**: Discord verification, trust, and GDPR-style transparency require stable public URLs for Privacy and Terms.

**Acceptance Scenarios**:

1. **Given** a visitor opens `/privacy`, **When** the page loads, **Then** they see a complete Privacy Policy covering what data is stored, why, retention, processors, user rights (including deletion requests), children’s privacy, and contact methods.
2. **Given** a visitor opens `/terms`, **When** the page loads, **Then** they see Terms covering eligibility/age, acceptable use, virtual items, disclaimers, liability limits, enforcement, and contact.
3. **Given** any public page, **When** the visitor opens the footer, **Then** Privacy and Terms links are present and resolve to those dedicated routes.
4. **Given** existing project drafts in the bot repo (`PRIVACY.md`, `TERMS.md`), **When** the site ships, **Then** published site copy is consistent with those sources (or an explicitly approved update of them), with placeholders for support invite and contact email replaced by real values before go-live.

**Independent Test**: From home footer, open Privacy and Terms; skim required sections; confirm no broken links and no unresolved placeholders on the live/staging build.

---

### User Story 4 - Get Started Quickly (Priority: P2)

As a new manager who just invited the bot, I find a short “How to Get Started” path (on home and/or Features) that tells me the first commands or hubs to use so I am not stuck after install.

**Why this priority**: Reduces early churn and support load; valuable but not required for Discord verification.

**Independent Test**: Follow the Get Started steps from the site with a fresh Discord server that has the bot installed; reach first meaningful in-bot action using only the site’s guidance.

**Acceptance Scenarios**:

1. **Given** a visitor views Get Started, **When** they read the steps, **Then** they see an ordered list of 3–6 concrete actions (e.g. invite bot → register club → set squad → play a match → open development/store hubs).
2. **Given** Get Started mentions commands or hubs, **When** names are shown, **Then** they match current bot surfaces (no obsolete command names).

---

### User Story 5 - Contact / Support Without Leaving Context (Priority: P2)

As a visitor with a question or data request, I find a Contact / Support section that points to the support Discord and privacy contact path described in the Privacy Policy.

**Why this priority**: Completes trust loop for legal and product questions; low complexity.

**Independent Test**: From footer or Contact section, open support invite and confirm privacy contact instructions match the Privacy page.

**Acceptance Scenarios**:

1. **Given** a visitor seeks help, **When** they use Contact/Support, **Then** the primary path is the official support Discord invite.
2. **Given** a visitor needs a data deletion or privacy request, **When** they follow Contact guidance, **Then** instructions match the Privacy Policy contact section.

---

### User Story 6 - Optional Live Stats (Priority: P3)

As a visitor, I may see high-level public stats (e.g. active clubs or matches played) if a safe public data source exists; if not, the site still ships without stats.

**Why this priority**: Nice-to-have social proof; must not block v1 and must not expose private or sensitive data.

**Independent Test**: With stats enabled, numbers load or fail gracefully; with stats disabled, no empty error UI.

**Acceptance Scenarios**:

1. **Given** no public stats feed is configured for v1, **When** the site ships, **Then** no broken stats widgets appear (section omitted or static placeholder approved in content config).
2. **Given** a future public, non-sensitive stats source is added, **When** stats fail to load, **Then** the rest of the page remains usable and no secrets are exposed in the browser.

---

### Edge Cases

- Invite or Support URL missing / still a placeholder → build or release checklist fails; pages must not ship with `[SUPPORT_SERVER_INVITE]`-style placeholders.
- Visitor has JavaScript disabled or a slow network → core content (name, CTAs, features text, legal pages) remains readable; progressive enhancement only for motion/media.
- External Discord OAuth or invite page is down → site still explains the bot; error is Discord-side, CTAs remain labeled clearly.
- Deep link to `/privacy` or `/terms` shared by Discord verification → pages load without requiring the home page first.
- Very small screens / large text accessibility settings → layout does not clip primary CTAs or legal headings.
- Media (GIF/video) fails → feature copy and icons still communicate value.
- User expects account login on the website → site is informational only; no Discord account login required for v1.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Site MUST provide a public home page that presents ElevenBoss branding, a tagline, and primary Invite + Support CTAs above the fold on common phone and desktop viewports.
- **FR-002**: Site MUST provide a Features experience (dedicated page and/or substantial home section) covering Live Match Visuals, Squad Building, Player Evolution, League Competitions, Economy, and Training / Development Hub.
- **FR-003**: Site MUST expose Privacy Policy at a stable route `/privacy` and Terms at `/terms`.
- **FR-004**: Site MUST link Privacy and Terms from the global footer on all pages.
- **FR-005**: Invite CTA MUST open Discord’s bot authorization flow with scopes that allow the bot to join a server and register application commands.
- **FR-006**: Support CTA MUST open the official community/support Discord invite URL.
- **FR-007**: Site MUST be usable on mobile-first viewports and meet basic accessibility expectations (readable contrast, focusable controls, meaningful link text, keyboard-reachable primary CTAs).
- **FR-008**: Content (copy, feature blurbs, legal text, CTA URLs) MUST be maintainable without a CMS — editable config and/or markdown sources that a maintainer can update in the site repository.
- **FR-009**: Site MUST NOT require a database or authenticated user accounts for v1 core pages.
- **FR-010**: Site MUST NOT expose the Discord bot token, database credentials, or other secrets in client-visible code or pages.
- **FR-011**: Legal pages MUST present bot-specific Privacy and Terms content suitable for Discord verification and trust (data collected, use, retention, rights, acceptable use, disclaimers, age restriction aligned with Discord ToS / under-13 exclusion).
- **FR-012**: Site MUST include a How to Get Started path (section or page) with ordered onboarding steps aligned to current bot commands/hubs.
- **FR-013**: Site MUST include Contact/Support guidance pointing to the support community and privacy contact path.
- **FR-014**: Visual design MUST follow a dark, modern, football-inspired brand direction (deep blue/green bases, gold/cyan accents, tasteful pitch/football cues) without relying on cluttered emoji spam.
- **FR-015**: Motion, if present, MUST be subtle and must not prevent reading or using CTAs; respect reduced-motion preference where the platform allows.
- **FR-016**: Optional public stats are out of scope for v1 unless a safe public feed is explicitly approved; if added later, failures MUST degrade gracefully.
- **FR-017**: An Invite convenience route (e.g. `/invite`) MAY redirect or deep-link to the same Discord OAuth invite URL used by the primary CTA.
- **FR-018**: Site MUST be hostable on a free-tier static-friendly hosting plan with custom domain support and automatic deploys from Git.

### Key Entities

- **Marketing Page**: A public route with title, sections, and CTAs (Home, Features, Privacy, Terms, optional Invite redirect).
- **Feature Pillar**: A named game capability with short description and optional media/icon key.
- **CTA Link**: Typed link (invite | support | external) with label and destination URL.
- **Legal Document**: Versioned Privacy or Terms body with effective date and contact block.
- **Site Config**: Maintainer-editable settings for tagline, CTA URLs, feature list, and contact placeholders.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A first-time visitor can identify the product and start the Discord invite flow within 30 seconds of landing on the home page (timed walkthrough).
- **SC-002**: Privacy and Terms pages are reachable from a cold deep link and from the footer of every page in under two clicks.
- **SC-003**: On a representative phone and desktop viewport, primary CTAs and feature copy remain fully usable without horizontal scroll (manual QA checklist pass).
- **SC-004**: Automated or manual performance review of the home page scores at least 90 on core web vitals / Lighthouse Performance and Accessibility categories before launch (or documented exceptions with fixes scheduled).
- **SC-005**: A maintainer can update tagline, feature blurbs, or legal text by editing content files only — no redesign required — and publish via the normal Git deploy path.
- **SC-006**: Discord verification / trust reviewers can open `/privacy` and `/terms` and find bot-specific data practices and usage rules without contacting the owner first.
- **SC-007**: Zero secrets (bot token, service keys) appear in the public site source or network responses for static pages.
- **SC-008**: New managers following Get Started can name the first in-bot action to take after invite (spot-check with 3 naive testers or equivalent walkthrough).

## Assumptions

- The public site is a **separate Git repository** from the ElevenBoss bot monorepo (as requested), with content kept in sync with bot product reality (command names, feature list).
- Legal copy for v1 is based on the existing bot-repo drafts `PRIVACY.md` and `TERMS.md` (effective 11 July 2026), adapted for web (absolute links between Privacy ↔ Terms, real support invite and contact email filled before launch).
- Bot Client ID / OAuth invite URL and support server invite are known to the maintainer and supplied via site config / environment for public values only — not via bot token.
- v1 does **not** include a blog, CMS, user accounts, payments, or live match embeds from Discord.
- Optional live stats (active clubs, matches played) are deferred unless a read-only public endpoint is approved later.
- “How to Get Started” reflects current hubs: register/onboarding, `/squad`, matches, `/development`, `/store` — exact step list finalized in planning against live bot commands.
- Hosting targets a free static-friendly plan with Git-based deploys and optional custom domain; no server-side database for marketing pages.
- Brand typography prefers a clean sans body and a sporty display heading; exact font files chosen in the technical plan.
- Design/architecture blueprint details (stack choices, component inventory, deployment checklist) are produced in `/speckit.plan` and refined in `research.md` for this feature — this specification defines product outcomes only.

## Out of Scope (v1)

- In-site Discord OAuth login for managers
- Live bot online/offline status requiring privileged APIs
- Admin dashboards, analytics accounts, or A/B tooling beyond basic privacy-respecting traffic if the host provides it
- Localization beyond English
- App store listings or Top.gg page redesign (links may be added later as config)
- Changing Discord bot behavior, RPCs, or database schema

## Sitemap (Product Routes)

| Route | Purpose |
|-------|---------|
| `/` | Landing: hero, short value props, Get Started teaser, CTAs |
| `/features` | Full feature pillars + optional media + CTAs |
| `/privacy` | Privacy Policy |
| `/terms` | Terms of Service |
| `/invite` (optional) | Shortcut to Discord bot invite OAuth URL |

Footer on all routes: Features, Privacy, Terms, Support, Invite.
