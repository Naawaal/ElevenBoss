# ElevenBoss Development Rules for AI Agents

This document contains strict constraints and architecture rules for AI agents operating on this repository. Every agent MUST adhere to these rules without exception.

---

## 1. The Monorepo Rule
* The `packages/` directory contains **pure Python logic** only.
* Agents are **strictly forbidden** from importing `discord` or `discord.ext` anywhere inside `packages/`.
* Any Discord-related integration, UI rendering, cogs, or interaction logic must remain in `apps/discord_bot/`.

## 2. The State Rule
* Packages under `packages/` must remain completely stateless regarding external databases.
* They **must not** instantiate database clients (such as Supabase, SQLAlchemy, etc.) or perform direct database IO.
* Packages should accept raw data or Pydantic models as input, perform the necessary calculations/logic, and return clean Pydantic models or primitive types.

## 3. The Database Rule
* All complex mutations (such as user registration, player transactions/purchases, league resets) must be handled via **atomic Supabase RPCs** (stored procedures) or safe, transaction-like **upserts**.
* **Never** write application-level loops that execute multiple sequential `INSERT` or `UPDATE` queries if they can be combined or batched. This minimizes network round-trips and prevents half-applied states.

## 4. The UI Rule
* Discord slash commands must invoke `await interaction.response.defer(ephemeral=True)` (or `ephemeral=False` as appropriate) **immediately** at the start of command execution.
* This prevents Discord's built-in 3-second API timeout limit from being exceeded during database requests or external processing.

## 5. The SDD (Spec-Driven Development) Rule
* Any new features, command flows, database schema changes, or architectural decisions **MUST** be designed and documented in the `.specify/specs/v1.0.0/spec.md` and `.specify/specs/v1.0.0/plan.md` files **BEFORE** writing any code.
* Implementation must strictly adhere to the approved specifications and technical plans.
* Any refinements or deviations introduced during coding must be retroactively reconciled in the SDD documents so they remain the single source of truth for the codebase.

