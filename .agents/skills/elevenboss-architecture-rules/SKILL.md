---
name: elevenboss-architecture-rules
description: Enforces the strict architectural constraints of the ElevenBoss monorepo. Use whenever designing, modifying, or implementing features across the Discord bot, pure packages, or the Supabase database.
---

# ElevenBoss Architectural Rules

You must abide by these strict constraints when working in the ElevenBoss workspace.

## 1. The Monorepo Boundary
- **`packages/`**: Pure Python logic only. **Never** import `discord` or `discord.ext` here. No database IO or client instantiation. Accept raw data or Pydantic models, return clean primitive types or Pydantic models.
- **`apps/discord_bot/`**: All Discord cogs, UI rendering (embeds, views), and interactions live here. DB calls are also made from here.

## 2. Database & State
- All complex mutations (e.g., registration, transactions, leveling) must be done via **atomic Supabase RPCs** or batch upserts.
- **No sequential loop updates/inserts** in application code.
- **Columns are defined only in `supabase/migrations/`**. Never reference columns in code/RPCs unless they exist in an applied migration.
- Always check and extend `supabase/scripts/verify_required_schema.sql` when adding DB objects.

## 3. UI and Interaction
- Discord slash commands must invoke `await interaction.response.defer(ephemeral=...)` **immediately** at the start of execution to prevent 3-second timeouts.

## 4. Spec-Driven Development (SDD)
- All new features and schema changes must be documented in `.specify/specs/v1.0.0/spec.md` and `plan.md` **before** writing code.

## 5. Lazy Senior Dev (Ponytail Mode)
- **Delete over add**. **Boring over clever**.
- Check if it already exists or if standard library covers it.
- Root-cause fixes only—don't patch symptoms.

## 6. Centralized Progression & Economy
- XP goes through `apply_card_xp`.
- Coins go through `apply_club_economy`.
- Never mutate XP/levels or coins directly with an UPDATE statement from cogs.

Use this skill continuously when reasoning about the architecture or placing files, to avoid corrupting the boundaries of ElevenBoss.
