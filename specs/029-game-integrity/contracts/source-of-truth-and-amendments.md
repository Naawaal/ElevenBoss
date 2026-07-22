# Contract: Source of Truth & Amendments

**Parent**: [../spec.md](../spec.md)

## 1. Conflict resolution order

When two documents disagree on an integrity rule, apply the highest applicable layer that has explicitly spoken:

1. **US-42 epic invariants & principles** (`specs/029-game-integrity/spec.md`)
2. **Locked US-42.x child spec** for that domain
3. **Locked domain feature spec** (e.g. `026`, `017`, `025`)
4. **`.specify/specs/v1.0.0/spec.md`**
5. Informal notes / chat / closed `022` registry entries

Lower layers may add detail; they must not contradict higher layers without an amendment.

## 2. Overlay rule

| Domain | Sporting / product owner | Integrity overlay |
|--------|--------------------------|-------------------|
| Guild league calendar & results | `026` / `027` | US-42.5 |
| P2P marketplace UX & tax | `017` | US-42.6 |
| Economy faucets/sinks pipe | US-25 / economy migrations | US-42.7 |
| Platform monorepo / Discord / scheduler host | `.specify/memory/constitution.md` | Complementary — US-42 does not replace |

Overlays add: idempotency, exclusive states, catch-up, fail-closed, audit. They do **not** invent a second calendar, second market, or second coin pipe.

## 3. Amendment process

1. Propose change in a PR or Speckit clarify note against `029` (or child if child-only).
2. State which INV/principle changes and **why** (exploit closed, product change, ops necessity).
3. Update epic `spec.md` (+ checklist if needed) **before** implementing contradictory code.
4. Cascade: update affected child specs and domain overlays in the same change set when possible.
5. If manager-visible, update `change_log.md`.

## 4. Forbidden shadow patterns

- Second XP or coin mutation path “just for this feature”
- UI-only caps without RPC enforcement
- Admin one-off SQL that grants rewards without ledger/idempotency
- Discord presentation retry that re-calls grant RPCs without keys
- New slash command for integrity when an existing hub can surface the message

## 5. Citation requirement (SC-005)

Plans and PRs that mutate durable game state MUST include:

```text
US-42 / US-42.x — <one sentence: which invariants this protects>
```
