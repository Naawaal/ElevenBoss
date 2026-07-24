# Research: In-Discord Help Hub (`046`)

**Date**: 2026-07-24  
**Spec**: [spec.md](./spec.md)

## R1 — Where does help content live?

**Decision**: Single Python module `apps/discord_bot/core/help_catalog.py` (typed topic records + docs base URL). No JSON/YAML file, no DB table, no `packages/` module.

**Rationale**: Copy is edited by bot developers alongside Discord UX; Python constants get type-check + import without a loader. Spec requires “one structured editable source” and “load from memory” — a module import is enough. Ponytail: fewest files.

**Alternatives considered**:
| Option | Why rejected |
|--------|----------------|
| JSON under `assets/` | Extra IO/loader; no win for ~9 topics |
| `packages/help/` | Over-abstraction; content is Discord-facing prose |
| Per-topic markdown files | More moving parts for v1 |

---

## R2 — Hub navigation pattern

**Decision**: Non-persistent `discord.ui.View` with category `Button`s that `edit` the same message to the topic embed; topic view has Back + Link “Read More”; hub has Link “Full Documentation”. Owner check on button clicks (`interaction.user.id == owner_id`).

**Rationale**: Matches store/academy hub patterns; ephemeral guild help should not register persistent `add_view` in `main.py`. Timeout disables controls; stale clicks get “run `/help` again”.

**Alternatives considered**:
| Option | Why rejected |
|--------|----------------|
| Select menu for topics | One extra tap vs labeled buttons; 9 topics fit 2 rows |
| Persistent custom_id views | Useless for ephemeral-only sessions; restart complexity |
| New message per category | Clutters DM history; loses Back-on-same-message simplicity |

---

## R3 — Ephemeral guild vs DM

**Decision**: `ephemeral = interaction.guild_id is not None` (guild → True, DM → False). `/help` is **not** `@app_commands.guild_only()` so DMs work. Most other hubs stay guild-only; help is the exception.

**Rationale**: Spec FR-005 / US5. Ephemeral in DMs is unreliable/empty; non-ephemeral in guild pollutes channels.

**Alternatives considered**: Always ephemeral (breaks DM); always public (channel spam).

---

## R4 — Docs URL map

**Decision**: `DOCS_BASE = "https://www.jotbird.com/app"`. Each topic may set `docs_path` (e.g. `""` or a future path segment). `resolve_docs_url(docs_path)` returns `DOCS_BASE` when path is empty/None, else `urljoin`-style join without inventing broken deep pages. v1 may ship all topics with empty path (all Read More → hub) until jotbird docs pages exist.

**Rationale**: Spec assumption — deep pages may not exist; never link 404s. Website (`008`) today is marketing (`/`, `/features`, …), not a full in-app manual; `/app` is the user-requested extended docs entry.

**Alternatives considered**: Hard-code per-topic marketing `/features` anchors (wrong product surface); omit Link buttons (worse mobile UX).

---

## R5 — Commands Reference harvest

**Decision**: At Commands topic render, walk `interaction.client.tree.walk_commands()`, collect `qualified_name` + `description` for each `AppCommand` / `Command` leaf (include group subcommands like `battle friendly`). Mark restricted when `default_permissions` is set **or** the command has custom checks (e.g. `/admin` owner check) → append `*(Admin/owner only)*`. Format as compact lines; chunk across embed fields/pages only if Discord limits force it (prefer description + few fields first).

**Rationale**: FR-011 / SC-005 — list must track the live tree. Harvest only for Commands topic (not every hub open) keeps default `/help` fast.

**Alternatives considered**:
| Option | Why rejected |
|--------|----------------|
| Hand-maintained command table in catalog | Rots the day a cog ships |
| Cache forever at startup | Misses mid-process sync edge cases; walk is cheap |
| Hide admin commands | Spec requires showing them with a note |

---

## R6 — Unregistered emphasis without blocking

**Decision**: After defer, best-effort `players` select `discord_id` / `maybe_single`. If no row → hub description includes a clear “Start here: Getting Started → `/register`” cue. On any client/timeout/error → render normal hub (fail-open). Static catalog never waits on DB.

**Rationale**: FR-015 / FR-010 / edge case latency. Do **not** call `ensure_registered` (that blocks unregistered users from help).

**Alternatives considered**: Always emphasize Getting Started (noisy for veterans); hard-require DB (violates SC-006).

---

## R7 — Topic autocomplete

**Decision**: Optional `topic: str` on `/help` with autocomplete returning catalog `id` / display label pairs (filter by `current`). Invalid topic → ephemeral error embed listing valid topics **or** fall through to hub with a one-line notice (prefer hub + notice for friendliness).

**Rationale**: US2 / FR-004. Choices capped at Discord’s 25 autocomplete results (we have 9).

---

## R8 — Content accuracy vs inventing mechanics

**Decision**: Topic bodies must describe **live** hubs/commands only (`/register`, `/battle`, `/squad`, `/development`, `/store`, `/marketplace`, `/league`, …). Ranked = “coming soon”. Gems/tax/discovery only if already live in bot copy elsewhere (store already shows gems). Prefer pointing to the hub command over restating every RPC formula.

**Rationale**: Spec assumption + integrity — help is documentation, not a second rulebook that drifts from RPCs.

---

## R9 — Brand / visuals

**Decision**: Embed `color=0x00FF87` (existing bot green). Category emoji on button labels and embed titles. No new asset pack required.

**Rationale**: Matches store/squad/marketplace hubs; FR-013.

---

## Resolved clarifications

No open `NEEDS CLARIFICATION` items remain from Technical Context — all choices above are defaults within the approved spec.
