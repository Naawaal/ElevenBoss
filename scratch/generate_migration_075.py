"""Generate supabase/migrations/075_player_card_state_guards.sql (one-shot)."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
M062 = (ROOT / "supabase/migrations/062_p2p_transfer_market.sql").read_text(encoding="utf-8")
M061 = (ROOT / "supabase/migrations/061_tier_fatigue_rebalance.sql").read_text(encoding="utf-8")
M066 = (ROOT / "supabase/migrations/066_dev_hub_recovery.sql").read_text(encoding="utf-8")
M050 = (ROOT / "supabase/migrations/050_fatigue_injury_hospital.sql").read_text(encoding="utf-8")
M038 = (ROOT / "supabase/migrations/038_audit_hardening_followup.sql").read_text(encoding="utf-8")
M047 = (ROOT / "supabase/migrations/047_audit_remediation.sql").read_text(encoding="utf-8")
M053 = (ROOT / "supabase/migrations/053_retirement_lifecycle_fixes.sql").read_text(encoding="utf-8")
M060 = (ROOT / "supabase/migrations/060_youth_academy_workflow.sql").read_text(encoding="utf-8")
OUT = ROOT / "supabase/migrations/075_player_card_state_guards.sql"


def extract_fn(text: str, name: str) -> str:
    pat = rf"(CREATE OR REPLACE FUNCTION public\.{name}\([\s\S]*?\n\$\$;)"
    m = re.search(pat, text)
    if not m:
        raise SystemExit(f"missing {name}")
    return m.group(1)


def inject_after(body: str, needle: str, inject: str) -> str:
    if "assert_card_action_allowed" in body and inject.split("'")[1] in body:
        # already has this action wire — still allow multiple different actions
        pass
    if inject.strip() in body:
        return body
    idx = body.find(needle)
    if idx < 0:
        raise SystemExit(f"needle not found for inject: {needle[:80]!r}")
    end = idx + len(needle)
    return body[:end] + "\n" + inject + body[end:]


ASSERT_SQL = r"""
-- 075_player_card_state_guards.sql
-- US-42.2: shared card-state assert + wire Critical (and soft) gap RPCs.

CREATE OR REPLACE FUNCTION public.card_primary_state(p_card_id UUID)
RETURNS TEXT
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_owner BIGINT;
    v_retired BOOLEAN;
    v_hospital BOOLEAN;
    v_academy BOOLEAN;
    v_listed BOOLEAN;
    v_evolving BOOLEAN;
    v_training BOOLEAN;
    v_in_xi BOOLEAN;
BEGIN
    SELECT owner_id,
           COALESCE(is_retired, FALSE),
           COALESCE(in_hospital, FALSE),
           COALESCE(in_academy, FALSE)
    INTO v_owner, v_retired, v_hospital, v_academy
    FROM public.player_cards
    WHERE id = p_card_id;

    IF NOT FOUND THEN
        RETURN NULL;
    END IF;

    IF v_retired THEN
        RETURN 'Retired';
    END IF;

    v_listed := EXISTS (
        SELECT 1 FROM public.transfer_listings
        WHERE card_id = p_card_id AND status = 'active'
    );
    IF v_listed THEN
        RETURN 'Listed';
    END IF;

    IF v_hospital THEN
        RETURN 'Hospitalized';
    END IF;

    v_evolving := EXISTS (
        SELECT 1 FROM public.active_evolutions
        WHERE card_id = p_card_id AND status = 'active'
    );
    IF v_evolving THEN
        RETURN 'Evolving';
    END IF;

    v_training := EXISTS (
        SELECT 1 FROM public.active_training
        WHERE card_id = p_card_id AND end_time > NOW()
    );
    IF v_training THEN
        RETURN 'TrainingBusy';
    END IF;

    IF v_academy THEN
        RETURN 'InAcademy';
    END IF;

    v_in_xi := EXISTS (
        SELECT 1 FROM public.squad_assignments
        WHERE player_card_id = p_card_id
    );
    IF v_in_xi THEN
        RETURN 'InXI';
    END IF;

    RETURN 'RosterFree';
END;
$$;

CREATE OR REPLACE FUNCTION public.assert_card_action_allowed(
    p_owner_id BIGINT,
    p_card_id UUID,
    p_action TEXT
) RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    v_owner BIGINT;
    v_retired BOOLEAN;
    v_hospital BOOLEAN;
    v_academy BOOLEAN;
    v_injury INTEGER;
    v_listed BOOLEAN;
    v_evolving BOOLEAN;
    v_training BOOLEAN;
    v_in_xi BOOLEAN;
    v_busy INT := 0;
    v_primary TEXT;
    v_mutation BOOLEAN;
BEGIN
    IF p_action IS NULL OR btrim(p_action) = '' THEN
        RAISE EXCEPTION 'CARD_STATE: missing action';
    END IF;

    SELECT owner_id,
           COALESCE(is_retired, FALSE),
           COALESCE(in_hospital, FALSE),
           COALESCE(in_academy, FALSE),
           injury_tier
    INTO v_owner, v_retired, v_hospital, v_academy, v_injury
    FROM public.player_cards
    WHERE id = p_card_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Player card not found or not owned';
    END IF;

    IF v_owner IS DISTINCT FROM p_owner_id THEN
        RAISE EXCEPTION 'Player card not found or not owned';
    END IF;

    v_listed := EXISTS (
        SELECT 1 FROM public.transfer_listings
        WHERE card_id = p_card_id AND status = 'active'
    );
    v_evolving := EXISTS (
        SELECT 1 FROM public.active_evolutions
        WHERE card_id = p_card_id AND status = 'active'
    );
    v_training := EXISTS (
        SELECT 1 FROM public.active_training
        WHERE card_id = p_card_id AND end_time > NOW()
    );
    v_in_xi := EXISTS (
        SELECT 1 FROM public.squad_assignments
        WHERE player_card_id = p_card_id
    );

    IF v_retired THEN v_busy := v_busy + 1; END IF;
    IF v_listed THEN v_busy := v_busy + 1; END IF;
    IF v_hospital THEN v_busy := v_busy + 1; END IF;
    IF v_evolving THEN v_busy := v_busy + 1; END IF;
    IF v_training THEN v_busy := v_busy + 1; END IF;
    IF v_academy THEN v_busy := v_busy + 1; END IF;

    IF v_busy > 1 OR (v_busy >= 1 AND v_in_xi) THEN
        RAISE EXCEPTION 'CARD_STATE: state_conflict';
    END IF;

    -- Priority mirrors packages/player_engine/card_state.py
    IF v_retired THEN
        v_primary := 'Retired';
    ELSIF v_listed THEN
        v_primary := 'Listed';
    ELSIF v_hospital THEN
        v_primary := 'Hospitalized';
    ELSIF v_evolving THEN
        v_primary := 'Evolving';
    ELSIF v_training THEN
        v_primary := 'TrainingBusy';
    ELSIF v_academy THEN
        v_primary := 'InAcademy';
    ELSIF v_in_xi THEN
        v_primary := 'InXI';
    ELSE
        v_primary := 'RosterFree';
    END IF;

    v_mutation := p_action IS DISTINCT FROM 'view_profile';
    IF v_mutation THEN
        PERFORM public.assert_not_in_match(p_owner_id);
    END IF;

    -- Matrix Allow sets (spec §B.5)
    IF p_action = 'view_profile' THEN
        RETURN;
    ELSIF p_action = 'assign_xi' THEN
        IF v_primary IS DISTINCT FROM 'RosterFree' THEN
            RAISE EXCEPTION 'CARD_STATE: % blocks assign_xi', v_primary;
        END IF;
    ELSIF p_action = 'bench' THEN
        IF v_primary IS DISTINCT FROM 'InXI' THEN
            RAISE EXCEPTION 'CARD_STATE: % blocks bench', v_primary;
        END IF;
    ELSIF p_action = 'match_include' THEN
        IF v_primary NOT IN ('RosterFree', 'InXI') THEN
            RAISE EXCEPTION 'CARD_STATE: % blocks match_include', v_primary;
        END IF;
    ELSIF p_action = 'drill' THEN
        IF v_primary NOT IN ('RosterFree', 'InXI') THEN
            RAISE EXCEPTION 'CARD_STATE: % blocks drill', v_primary;
        END IF;
    ELSIF p_action = 'fusion' THEN
        IF v_primary IS DISTINCT FROM 'RosterFree' THEN
            RAISE EXCEPTION 'CARD_STATE: % blocks fusion', v_primary;
        END IF;
    ELSIF p_action = 'allocate' THEN
        IF v_primary NOT IN ('RosterFree', 'InXI') THEN
            RAISE EXCEPTION 'CARD_STATE: % blocks allocate', v_primary;
        END IF;
    ELSIF p_action = 'recover_fatigue' THEN
        IF v_primary NOT IN ('RosterFree', 'InXI') THEN
            RAISE EXCEPTION 'CARD_STATE: % blocks recover_fatigue', v_primary;
        END IF;
    ELSIF p_action = 'start_evolution' THEN
        IF v_primary IS DISTINCT FROM 'RosterFree' THEN
            RAISE EXCEPTION 'CARD_STATE: % blocks start_evolution', v_primary;
        END IF;
    ELSIF p_action IN ('claim_evolution', 'cancel_evolution') THEN
        IF v_primary IS DISTINCT FROM 'Evolving' THEN
            RAISE EXCEPTION 'CARD_STATE: % blocks %', v_primary, p_action;
        END IF;
    ELSIF p_action = 'admit_hospital' THEN
        IF v_primary IS DISTINCT FROM 'RosterFree' THEN
            RAISE EXCEPTION 'CARD_STATE: % blocks admit_hospital', v_primary;
        END IF;
    ELSIF p_action = 'discharge_hospital' THEN
        IF v_primary IS DISTINCT FROM 'Hospitalized' THEN
            RAISE EXCEPTION 'CARD_STATE: % blocks discharge_hospital', v_primary;
        END IF;
    ELSIF p_action = 'list_transfer' THEN
        IF v_primary IS DISTINCT FROM 'RosterFree' THEN
            RAISE EXCEPTION 'CARD_STATE: % blocks list_transfer', v_primary;
        END IF;
        -- InjuryPlayOn modifier (fatigue alone does NOT block list)
        IF v_injury IS NOT NULL OR v_hospital THEN
            RAISE EXCEPTION 'CARD_STATE: injury blocks list_transfer';
        END IF;
    ELSIF p_action = 'cancel_listing' THEN
        IF v_primary IS DISTINCT FROM 'Listed' THEN
            RAISE EXCEPTION 'CARD_STATE: % blocks cancel_listing', v_primary;
        END IF;
    ELSIF p_action = 'agent_sell' THEN
        IF v_primary IS DISTINCT FROM 'RosterFree' THEN
            RAISE EXCEPTION 'CARD_STATE: % blocks agent_sell', v_primary;
        END IF;
        IF v_injury IS NOT NULL OR v_hospital THEN
            RAISE EXCEPTION 'CARD_STATE: injury blocks agent_sell';
        END IF;
    ELSIF p_action = 'academy_seat' THEN
        IF v_primary IS DISTINCT FROM 'RosterFree' THEN
            RAISE EXCEPTION 'CARD_STATE: % blocks academy_seat', v_primary;
        END IF;
    ELSIF p_action IN ('academy_promote', 'academy_release') THEN
        IF v_primary IS DISTINCT FROM 'InAcademy' THEN
            RAISE EXCEPTION 'CARD_STATE: % blocks %', v_primary, p_action;
        END IF;
    ELSIF p_action = 'retire' THEN
        IF v_primary NOT IN ('RosterFree', 'InXI') THEN
            RAISE EXCEPTION 'CARD_STATE: % blocks retire', v_primary;
        END IF;
    ELSE
        -- Default: only RosterFree / InXI for unknown future mutations
        IF v_primary NOT IN ('RosterFree', 'InXI') THEN
            RAISE EXCEPTION 'CARD_STATE: % blocks %', v_primary, p_action;
        END IF;
    END IF;
END;
$$;

GRANT ALL PRIVILEGES ON FUNCTION public.card_primary_state(UUID)
    TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.assert_card_action_allowed(BIGINT, UUID, TEXT)
    TO anon, authenticated, service_role;
"""


def main() -> None:
    drill = extract_fn(M062, "process_stat_drill")
    drill = inject_after(
        drill,
        "PERFORM public.assert_card_not_on_transfer_list(p_card_id);",
        "    PERFORM public.assert_card_action_allowed(p_owner_id, p_card_id, 'drill');",
    )

    evo = extract_fn(M062, "start_player_evolution")
    evo = inject_after(
        evo,
        "PERFORM public.assert_card_not_on_transfer_list(p_card_id);",
        "    PERFORM public.assert_card_action_allowed(p_owner_id, p_card_id, 'start_evolution');",
    )

    swap = extract_fn(M062, "swap_squad_players")
    swap = inject_after(
        swap,
        "PERFORM public.assert_card_not_on_transfer_list(p_reserve_card_id);",
        "    PERFORM public.assert_card_action_allowed(p_discord_id, p_reserve_card_id, 'assign_xi');",
    )

    admit = extract_fn(M061, "admit_to_hospital")
    if "assert_card_action_allowed" not in admit:
        admit = admit.replace(
            "BEGIN\n    SELECT injury_tier INTO v_tier",
            "BEGIN\n    PERFORM public.assert_card_action_allowed("
            "p_owner_id, p_player_card_id, 'admit_hospital');\n\n"
            "    SELECT injury_tier INTO v_tier",
            1,
        )

    fodder = extract_fn(M062, "train_with_fodder")
    fodder = inject_after(
        fodder,
        "PERFORM public.assert_card_not_on_transfer_list(p_fodder_id);",
        "    PERFORM public.assert_card_action_allowed(p_owner_id, p_target_id, 'fusion');\n"
        "    PERFORM public.assert_card_action_allowed(p_owner_id, p_fodder_id, 'fusion');",
    )

    alloc = extract_fn(M062, "allocate_skill_point")
    alloc = inject_after(
        alloc,
        "PERFORM public.assert_card_not_on_transfer_list(p_card_id);",
        "    PERFORM public.assert_card_action_allowed(p_owner_id, p_card_id, 'allocate');",
    )

    agent = extract_fn(M062, "process_agent_sale")
    agent = inject_after(
        agent,
        "PERFORM public.assert_card_not_on_transfer_list(p_card_id);",
        "    PERFORM public.assert_card_action_allowed(p_club_id, p_card_id, 'agent_sell');",
    )

    cancel = extract_fn(M062, "cancel_transfer_listing")
    if "assert_card_action_allowed" not in cancel:
        cancel = cancel.replace(
            "IF NOT FOUND THEN\n"
            "        RAISE EXCEPTION 'Active listing not found or not owned';\n"
            "    END IF;\n\n"
            "    UPDATE public.transfer_listings",
            "IF NOT FOUND THEN\n"
            "        RAISE EXCEPTION 'Active listing not found or not owned';\n"
            "    END IF;\n\n"
            "    PERFORM public.assert_card_action_allowed("
            "p_seller_id, v_listing.card_id, 'cancel_listing');\n\n"
            "    UPDATE public.transfer_listings",
            1,
        )

    # recovery batch — loop inject per card after list assert
    recovery = extract_fn(M066, "process_recovery_batch")
    recovery = inject_after(
        recovery,
        "PERFORM public.assert_card_not_on_transfer_list(v_card_id);",
        "        PERFORM public.assert_card_action_allowed("
        "p_owner_id, v_card_id, 'recover_fatigue');",
    )

    discharge = extract_fn(M050, "discharge_from_hospital")
    if "assert_card_action_allowed" not in discharge:
        discharge = discharge.replace(
            "BEGIN\n    UPDATE public.hospital_patients",
            "BEGIN\n    PERFORM public.assert_card_action_allowed("
            "p_owner_id, p_player_card_id, 'discharge_hospital');\n\n"
            "    UPDATE public.hospital_patients",
            1,
        )

    claim = extract_fn(M038, "claim_evolution_reward")
    if "assert_card_action_allowed" not in claim:
        claim = claim.replace(
            "IF v_card_id IS NULL THEN\n"
            "        RAISE EXCEPTION 'Evolution not found';\n"
            "    END IF;\n"
            "    IF v_status <> 'active' THEN",
            "IF v_card_id IS NULL THEN\n"
            "        RAISE EXCEPTION 'Evolution not found';\n"
            "    END IF;\n"
            "    PERFORM public.assert_card_action_allowed("
            "p_owner_id, v_card_id, 'claim_evolution');\n"
            "    IF v_status <> 'active' THEN",
            1,
        )

    cancel_evo = extract_fn(M047, "cancel_player_evolution")
    if "assert_card_action_allowed" not in cancel_evo:
        cancel_evo = cancel_evo.replace(
            "IF v_evo.status <> 'active' THEN\n"
            "        RAISE EXCEPTION 'Only active evolutions can be cancelled';\n"
            "    END IF;\n\n"
            "    v_econ := public.apply_club_economy(",
            "IF v_evo.status <> 'active' THEN\n"
            "        RAISE EXCEPTION 'Only active evolutions can be cancelled';\n"
            "    END IF;\n\n"
            "    PERFORM public.assert_card_action_allowed("
            "p_owner_id, v_evo.card_id, 'cancel_evolution');\n\n"
            "    v_econ := public.apply_club_economy(",
            1,
        )

    promote = extract_fn(M060, "promote_academy_player")
    if "assert_card_action_allowed" not in promote:
        promote = promote.replace(
            "IF NOT COALESCE(v_card.in_academy, FALSE) THEN\n"
            "        RAISE EXCEPTION 'Not an academy player';\n"
            "    END IF;\n\n"
            "    v_cap := public.get_game_config_int('senior_roster_cap', 48)::INTEGER;",
            "IF NOT COALESCE(v_card.in_academy, FALSE) THEN\n"
            "        RAISE EXCEPTION 'Not an academy player';\n"
            "    END IF;\n\n"
            "    PERFORM public.assert_card_action_allowed("
            "p_owner_id, p_card_id, 'academy_promote');\n\n"
            "    v_cap := public.get_game_config_int('senior_roster_cap', 48)::INTEGER;",
            1,
        )

    release = extract_fn(M060, "release_academy_player")
    if "assert_card_action_allowed" not in release:
        release = release.replace(
            "IF NOT FOUND THEN\n"
            "        RAISE EXCEPTION 'Not an academy player';\n"
            "    END IF;\n\n"
            "    DELETE FROM public.squad_assignments WHERE player_card_id = p_card_id;",
            "IF NOT FOUND THEN\n"
            "        RAISE EXCEPTION 'Not an academy player';\n"
            "    END IF;\n\n"
            "    PERFORM public.assert_card_action_allowed("
            "p_owner_id, p_card_id, 'academy_release');\n\n"
            "    DELETE FROM public.squad_assignments WHERE player_card_id = p_card_id;",
            1,
        )

    retire = extract_fn(M053, "retire_player_card")
    if "assert_card_action_allowed" not in retire:
        retire = retire.replace(
            "IF v_owner IS NULL THEN\n"
            "        RAISE EXCEPTION 'Card not found or already retired';\n"
            "    END IF;\n\n"
            "    SELECT position_slot INTO v_slot",
            "IF v_owner IS NULL THEN\n"
            "        RAISE EXCEPTION 'Card not found or already retired';\n"
            "    END IF;\n\n"
            "    PERFORM public.assert_card_action_allowed(v_owner, p_card_id, 'retire');\n\n"
            "    SELECT position_slot INTO v_slot",
            1,
        )

    # create_transfer_listing — after card locked + ownership (avoid lock-order flip)
    create_list = extract_fn(M062, "create_transfer_listing")
    if "assert_card_action_allowed" not in create_list:
        create_list = create_list.replace(
            "IF NOT FOUND THEN\n"
            "        RAISE EXCEPTION 'Player card not found or not owned';\n"
            "    END IF;\n"
            "    IF COALESCE(v_card.is_retired, FALSE) THEN",
            "IF NOT FOUND THEN\n"
            "        RAISE EXCEPTION 'Player card not found or not owned';\n"
            "    END IF;\n"
            "    PERFORM public.assert_card_action_allowed(p_seller_id, p_card_id, 'list_transfer');\n"
            "    IF COALESCE(v_card.is_retired, FALSE) THEN",
            1,
        )

    parts = [
        ASSERT_SQL.strip() + "\n",
        "-- ---------------------------------------------------------------------------",
        "-- Critical gap wires (from rpc-guard-audit.md)",
        "-- ---------------------------------------------------------------------------",
        "",
        admit,
        "",
        swap,
        "",
        drill,
        "",
        evo,
        "",
        "-- Soft / remaining gap wires",
        "",
        create_list,
        "",
        cancel,
        "",
        agent,
        "",
        fodder,
        "",
        alloc,
        "",
        recovery,
        "",
        discharge,
        "",
        claim,
        "",
        cancel_evo,
        "",
        promote,
        "",
        release,
        "",
        retire,
        "",
        """
-- ---------------------------------------------------------------------------
-- Schema guard
-- ---------------------------------------------------------------------------
DO $$
DECLARE
    missing TEXT := '';
BEGIN
    IF to_regprocedure('public.assert_card_action_allowed(bigint,uuid,text)') IS NULL THEN
        missing := missing || 'assert_card_action_allowed ';
    END IF;
    IF to_regprocedure('public.card_primary_state(uuid)') IS NULL THEN
        missing := missing || 'card_primary_state ';
    END IF;
    IF missing <> '' THEN
        RAISE EXCEPTION '075 schema guard failed: %', missing;
    END IF;
END;
$$;
""".strip(),
        "",
    ]
    OUT.write_text("\n".join(parts) + "\n", encoding="utf-8")
    print(f"Wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
