# Feature Specification: In-Discord Help Hub

**Feature Branch**: `046-help-hub`

**Created**: 2026-07-24

**Status**: Implemented — Discord smoke recommended after bot restart / command sync

**Input**: User description: "Comprehensive `/help` slash command as the single source of in-Discord documentation — interactive hub with category buttons, optional `/help <topic>` autocomplete, embedded coverage of major systems, Commands Reference harvested from the live command tree, and links to extended docs at https://www.jotbird.com/app. Ephemeral in servers; non-ephemeral in DMs. Ponytail-compliant, maintainable content, no over-engineering."

**Parent / related**: New player-facing documentation surface. Complements public site (`specs/008-public-website`) and existing hubs (`/register`, `/battle`, `/squad`, `/development`, `/store`, `/marketplace`, `/league`, etc.). Does **not** change game mechanics, economy, or schema. Approves **one** new slash command: `/help` (explicitly in scope for this feature).

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Browse help from an interactive hub (Priority: P1)

A manager (new or experienced) runs `/help` and sees a clear hub embed with category buttons. They tap a category, read a focused explanation of that system in Discord, use Back to return to the hub, and optionally open Full Documentation on the website — without cluttering the channel for other members.

**Why this priority**: This is the core value — answers stay in Discord, navigation is obvious, and channel noise stays low. Without the hub, other stories have nowhere to land.

**Independent Test**: In a guild channel, run `/help` → see hub → open two different categories → Back each time → open Full Documentation link target → confirm only the invoking user sees the ephemeral help flow.

**Acceptance Scenarios**:

1. **Given** a manager in a server channel, **When** they run `/help` with no topic, **Then** they receive an ephemeral hub embed listing the help categories with working navigation controls.
2. **Given** the hub is open, **When** they select a category, **Then** the message updates (or is replaced) with that category’s detailed help content and a Back control that returns to the hub.
3. **Given** any hub or category view, **When** they use Full Documentation / Read More, **Then** they get a working link to the extended docs site (base or topic page as defined for that surface).
4. **Given** another member in the same channel, **When** the first manager uses `/help`, **Then** the other member does not see the help embeds (ephemeral).

---

### User Story 2 — Jump straight to a topic (Priority: P2)

An experienced manager who already knows the category name runs `/help <topic>` (with autocomplete) and lands on that topic’s embed immediately, still with Back to hub and external doc link where appropriate.

**Why this priority**: Speeds power users and reduces button hops; secondary to the button-first hub which remains the primary interface for discovery.

**Independent Test**: Invoke `/help` with an autocomplete-suggested topic (e.g. league) → topic embed appears without visiting the hub first → Back returns to hub.

**Acceptance Scenarios**:

1. **Given** `/help` supports a topic option, **When** the manager types `/help` and focuses the topic field, **Then** they see autocomplete choices for the defined help topics.
2. **Given** a valid topic, **When** they submit `/help topic:<name>`, **Then** they see that topic’s content (same quality as button navigation) with Back to hub.
3. **Given** an unrecognized or empty topic string (if free-text is allowed), **When** submitted, **Then** they get a clear recovery path (hub or “unknown topic” with suggestions) — never a raw error.

---

### User Story 3 — Learn systems without leaving Discord (Priority: P1)

A manager reads accurate, concise coverage of major systems from the help embeds themselves (not “go read the website” as the only answer). Website links are optional deepening, not a substitute for core explanations.

**Why this priority**: The product promise is in-Discord documentation; external docs are extended reading.

**Independent Test**: Open each required category; confirm each contains substantive embedded guidance covering the outline in Content Coverage, plus a Read More / docs cue.

**Acceptance Scenarios**:

1. **Given** each required help category, **When** opened, **Then** the embed contains enough embedded text for a manager to understand the system’s purpose and next in-bot actions (slash hubs / key flows) without opening the website.
2. **Given** a category with a mapped docs page, **When** shown, **Then** a small footer and/or Read More control points at the corresponding jotbird docs URL (or the docs hub if no deep page exists yet).
3. **Given** “coming soon” features (e.g. Ranked), **When** Battle help is shown, **Then** they are labeled as coming soon — not presented as live commands.

---

### User Story 4 — Discover all slash commands in one place (Priority: P2)

A manager opens Commands Reference and sees a concise list of the bot’s slash commands with short descriptions. Admin-only commands appear with an “Admin only” (or equivalent) note. The list stays aligned with what the bot actually registers.

**Why this priority**: Reduces “what command do I use?” support load; must not drift from the live command tree.

**Independent Test**: Open Commands Reference; verify every user-facing registered slash command appears with a description; verify admin-restricted commands are marked; after adding/removing a command in a test bot, the harvested list reflects the tree without a separate manual content edit for that entry.

**Acceptance Scenarios**:

1. **Given** the bot has registered slash commands, **When** Commands Reference is opened, **Then** the manager sees a concise name + description list derived from the live command tree (not a stale hand-maintained-only duplicate of names).
2. **Given** admin-only or owner-only commands exist, **When** listed, **Then** they are still shown with a clear Admin/owner-only note so server owners can discover them.
3. **Given** the command list is long, **When** shown, **Then** it remains readable (fields and/or simple paging) without requiring the website for the basic list.

---

### User Story 5 — New managers and DM users are guided (Priority: P3)

A user with no club yet sees Getting Started emphasized. A user who DMs `/help` still gets the full guide (visible in the DM, not forced-ephemeral in a way that breaks DM UX).

**Why this priority**: Improves onboarding and DM support; not required for the hub MVP to work for registered managers.

**Independent Test**: Unregistered user runs `/help` in a server → hub highlights Getting Started; same user DMs `/help` → help appears in DM as a normal DM reply.

**Acceptance Scenarios**:

1. **Given** the invoking user has no registered club, **When** they open `/help` (hub), **Then** Getting Started is visually prominent (e.g. first category, emphasized copy, or clear “start here” cue).
2. **Given** `/help` is invoked in a DM with the bot, **When** the response is sent, **Then** help is shown in that DM without relying on guild-ephemeral-only behavior that would hide or fail the reply.
3. **Given** high bot load, **When** `/help` is invoked, **Then** the hub/topic still appears promptly from in-memory help content (no database round-trip required to render static help text).

---

### Edge Cases

- **No club yet**: Getting Started prominent; other categories still reachable.
- **DM vs guild**: Guild → ephemeral; DM → non-ephemeral (standard DM message).
- **Stale view / bot restart**: Buttons on an old help message may expire or fail gracefully with a short “run `/help` again” cue — no crash.
- **Double-tap / rapid category switching**: Latest selection wins; no duplicate public spam (ephemeral/DM only).
- **Missing jotbird deep page**: Link falls back to `https://www.jotbird.com/app` rather than a broken URL.
- **Command tree empty or sync lag**: Commands Reference shows a clear empty/unavailable message, not a crash.
- **Permissions**: Help itself is available to all users who can use the bot; admin-only *listed* commands remain marked, not hidden.
- **Latency**: Static help must not wait on DB; optional club-existence check for “Getting Started” emphasis may be best-effort and must not block the hub if it fails (default to non-emphasized hub).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The product MUST expose a `/help` slash command as the single primary in-Discord documentation entry point.
- **FR-002**: `/help` with no topic MUST open an interactive Help Hub with category navigation controls for all required categories.
- **FR-003**: Category navigation MUST show detailed topic content and provide Back navigation to the Help Hub.
- **FR-004**: `/help` MUST support an optional topic parameter with autocomplete for direct topic access; button navigation remains the primary discovery UX.
- **FR-005**: Help responses MUST be ephemeral in guild channels and non-ephemeral in DMs.
- **FR-006**: Core help content for each required category MUST be embedded in Discord (text/fields), not replaced by external links alone.
- **FR-007**: The Help Hub MUST include a Full Documentation control linking to `https://www.jotbird.com/app`.
- **FR-008**: Each topic view MUST include a footer and/or Read More control linking to the topic’s mapped docs URL, falling back to `https://www.jotbird.com/app` when no deep link is configured.
- **FR-009**: Help content MUST be maintained in one structured, editable content source (central catalog) so copy updates do not require hunting through command handlers.
- **FR-010**: Static help text MUST load from memory at runtime (no DB dependency for rendering topic bodies).
- **FR-011**: Commands Reference MUST be generated from the bot’s registered command tree (names + descriptions), with admin/owner-restricted commands still listed and clearly labeled.
- **FR-012**: Help MUST NOT introduce game economy/progression mutations, new tables, or new hubs beyond `/help` itself.
- **FR-013**: Help visuals MUST follow ElevenBoss brand cues (consistent embed color/style and relevant category emoji) so the guide feels native to the bot.
- **FR-014**: Complex topics MAY use multiple embed fields or simple pagination, but MUST stay scannable — no essay walls without structure.
- **FR-015**: When the invoker has no club, the hub MUST emphasize Getting Started without blocking access to other categories.
- **FR-016**: Interaction failures on expired help views MUST fail closed with a short recovery hint to re-run `/help`.

### Required Help Categories (Content Coverage)

The hub MUST expose at least these categories (labels may be lightly renamed for clarity, but coverage must map 1:1):

| ID | Category | Embedded coverage MUST include |
|----|----------|--------------------------------|
| `getting-started` | Getting Started | Register/create club, first squad, where to go next; **Core Loop** summary (energy → matches → XP/leveling → skill points → growth) |
| `battle` | Battle & Matches | Bot Battles, Friendly Matches, Ranked (coming soon), live pitch visuals, commentary |
| `squad` | Squad & Formation | View squad, set formation, swap players, pitch visual meaning |
| `training` | Training & Development | `/development` drills, skill allocation, mentor transfusion (maxed → youth) |
| `evolutions` | Evolutions | Active tracks, requirements, rewards, how to start |
| `league` | League System | Seasonal leagues, registration, matchdays, divisions, rewards, automation |
| `economy` | Economy & Marketplace | Coins, gems (if live), energy refills/`/store`, P2P trading, listing, tax, price discovery |
| `hospital` | Hospital & Fatigue | Fatigue, injuries, recovery, hospital upgrades |
| `commands` | Commands Reference | Concise live slash-command list (harvested) + short descriptions |

### Key Entities

- **Help Topic**: A named category with title, short hub blurb, body fields, emoji, and optional docs URL path/slug.
- **Help Hub**: Top-level navigation surface listing topics + Full Documentation.
- **Commands Snapshot**: Read-only projection of registered slash commands (name, description, restriction flag) used only for Commands Reference.
- **Docs Link Map**: Per-topic (and hub) URL pointing at jotbird extended docs, with hub fallback.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A new manager can open `/help` and reach Getting Started guidance in under 15 seconds (one command + at most one tap).
- **SC-002**: A manager can answer “how does X work?” for any required category without leaving Discord for the core explanation (website optional).
- **SC-003**: 100% of required categories are reachable from the hub; Back returns to the hub from every category view.
- **SC-004**: In guild channels, help is visible only to the invoking user (ephemeral); in DMs, help is visible in the DM thread.
- **SC-005**: Commands Reference lists every currently registered user-visible slash command name from the live tree, with admin/owner commands marked — verified by comparing the embed to the bot’s command registration.
- **SC-006**: Help hub/topic first paint does not depend on database availability for static copy (still works if DB is slow/down, aside from optional club-emphasis check).
- **SC-007**: Content editors can update a topic’s copy by changing the central help catalog only (no need to edit multiple unrelated command modules for prose).

## Assumptions

- Exact jotbird deep-link paths per topic may not all exist yet; a curated URL map ships with help content, and any missing deep link uses `https://www.jotbird.com/app`.
- Ranked matches remain “coming soon” in help copy until a separate feature ships them.
- Gems / marketplace tax / discovery wording reflects **currently live** bot behavior; help copy must not invent mechanics that are not in production.
- One new slash command (`/help`) is explicitly approved by this spec; no additional slash commands or parallel “docs” hubs.
- Optional club lookup for Getting Started emphasis is best-effort; failure defaults to a normal hub without blocking.
- Simple multi-field embeds are preferred over elaborate multi-page wizards; pagination only if Discord field/length limits force it.
- Localization is out of scope (English only for v1).
- Website content authorship on jotbird is out of scope except linking; Discord embeds are the owned deliverable of this feature.
- Technical layout (cog module, catalog file format, view classes) is deferred to `/speckit.plan` and MUST stay Ponytail-minimal: one content catalog, one help command surface, ephemeral/DM branching, command-tree harvest for Commands Reference.

## Out of Scope

- Building or rewriting jotbird website pages
- In-help tutorials that mutate game state (guided register wizards that run RPCs beyond linking to `/register`)
- AI chat support / ticket systems
- Per-guild custom help text
- Video/GIF embeds as a requirement (optional later)
- Changing existing hub commands’ behavior beyond linking to them from help copy

## Design Notes (product UX — for plan handoff)

### Hub → topic → Back

```text
/help
  └─ Hub embed
       ├─ [Getting Started] [Battle] [Squad] …
       ├─ [Commands]
       └─ [Full Documentation] → https://www.jotbird.com/app
            │
            ▼ (category)
       Topic embed (fields + Read More)
            └─ [Back] → Hub
```

### `/help topic:` shortcut

Same topic embed as button path; Back still returns to hub.

### Content maintenance principle

One catalog owns titles, bodies, emoji, and docs URLs. Commands Reference names/descriptions come from the live tree so they do not rot; only category prose is hand-authored.
