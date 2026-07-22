# Contract: Action Matrix Freeze

**Feature**: US-42.2  
**Source of truth**: [spec.md](../spec.md) §B.5

## Rule

Pure `can_perform_action` and SQL `assert_card_action_allowed` MUST implement the same Allow/Block outcomes for actions listed in `data-model.md` §3.

## MatchLocked

When overlay MatchLocked is present, all mutation actions Block; `view_profile` Allowed.

## Injury modifier

If `injury_tier` is set OR hospitalized → `list_transfer` and `agent_sell` Block (even if primary would otherwise allow list only when RosterFree without injury).

## Fatigue

Fatigue alone does not Block `list_transfer`.

## Change control

Matrix edits require amending `spec.md` §B.5 first, then pure + SQL together.
