# Data Model: In-Discord Help Hub (`046`)

**Storage**: Process memory only. **No** Postgres tables, migrations, or RPCs.

## Entities

### HelpTopic

| Field | Type | Rules |
|-------|------|-------|
| `id` | string | Stable slug; required set: `getting-started`, `battle`, `squad`, `training`, `evolutions`, `league`, `economy`, `hospital`, `commands` |
| `label` | string | Button + autocomplete display name |
| `emoji` | string | Leading emoji for buttons/titles |
| `hub_blurb` | string | One short line on the hub embed |
| `title` | string | Topic embed title |
| `fields` | list of `{name, value}` | Discord embed fields; each `value` must stay within Discord field limits; keep scannable |
| `docs_path` | string \| null | Optional path/fragment relative to docs base; empty/null → base URL only |
| `is_commands` | bool | If true, body fields may be empty/stub — Commands Reference injects harvested lines at render |

**Validation**:
- Exactly the nine required IDs exist in the catalog (tests assert set equality).
- `id` unique; autocomplete keys off `id`.
- No topic invents live mechanics not present in the bot.

### DocsLinkMap

| Field | Type | Rules |
|-------|------|-------|
| `DOCS_BASE` | const URL | `https://www.jotbird.com/app` |
| `resolve_docs_url(docs_path)` | function | Returns absolute https URL; never returns empty string |

**Hub Full Documentation** always uses `DOCS_BASE`.  
**Topic Read More** uses `resolve_docs_url(topic.docs_path)`.

### CommandEntry (harvest projection)

| Field | Type | Rules |
|-------|------|-------|
| `qualified_name` | string | e.g. `battle friendly`, `help` |
| `description` | string | From command registration; may be empty → show `(no description)` |
| `restricted` | bool | True if owner/admin checks or `default_permissions` imply restriction |

**Relationships**: Commands Reference topic render → list of `CommandEntry` → formatted text chunks → embed field(s). Not persisted.

### HelpSession (ephemeral UI state)

| Field | Type | Rules |
|-------|------|-------|
| `owner_id` | snowflake | Only this user may press category/Back buttons |
| `ephemeral` | bool | Captured at command invoke (guild vs DM) |
| `emphasize_getting_started` | bool | From best-effort club check |

No durable session store — state lives on the View instance until timeout.

## State transitions (UI only)

```text
[Invoke /help]
    ├─ topic missing/invalid → Hub
    └─ topic valid → Topic(id)
Hub --category--> Topic(id)
Topic --Back--> Hub
Hub/Topic --Link--> (external browser; no Discord state change)
View timeout → controls disabled; next click → recovery cue
```

## Non-entities

- No `help_views` table, no analytics events required for v1, no per-guild overrides.
