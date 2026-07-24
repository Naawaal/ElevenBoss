# Data Model: Match Engine V3 Production Rollout

**Feature**: `044-match-v3-rollout`  
**Schema owner**: Existing migration `083_match_engine_v3_events.sql` — **no new tables expected**

---

## 1. Reused entities

### `game_config` flags

| Key | Type | Default | Meaning |
|-----|------|---------|---------|
| `match_engine_v3_bot` | int/json `0`/`1` | `0` | New bot kicks use `nss_v3` |
| `match_engine_v3_league` | int/json `0`/`1` | `0` | New league live + auto-sim kicks use `nss_v3` |
| `match_engine_v3_friendly` | int/json `0`/`1` | `0` | New friendly kicks use `nss_v3` |

### `match_runs`

| Column | Role |
|--------|------|
| `engine_version` | `nss_v2` \| `nss_v3` — **pinned at create** |
| `simulation_schema_version` | Schema semantics pin (v3 uses Wave schema) |
| `status` / scores / snapshot | Unchanged recovery + settle lifecycle |

### `match_events` (append-only)

Durable V3 event stream for bot/league runs — source for projectors and recovery. Friendly may remain ephemeral per `041` research.

---

## 2. Read models (not tables)

### `Explanation` (Pydantic)

| Field | Meaning |
|-------|---------|
| `headline` | Short result-flavored summary |
| `turning_points` | Up to ~5 `{minute, type, causal_hint, seq, text_key?}` |
| `primary_turning_seq` | Optional seq of decisive moment |

### Discord display model

Flatten to embed field “How it was decided”: headline + ≤3 tip lines with humanized text.

---

## 3. State / transitions

```text
flag off  --ops enable--> new kicks pin nss_v3
flag on   --ops disable-> new kicks pin nss_v2
in-flight run -----------> always completes on pinned engine_version
```

---

## 4. Validation rules

1. Create-run MUST set `engine_version` from type flag at kickoff.  
2. Recovery MUST branch on stored pin, not current flag.  
3. Explainability MUST only cite events present in the stream.  
4. No new coin/XP columns or settlement tables in this feature.
)
