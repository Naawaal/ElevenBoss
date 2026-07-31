"""Build supabase/migrations/088_rarity_potential_guards.sql from live RPC dumps."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DUMP = ROOT / "scratch" / "live_rpc_defs_049"
OUT = ROOT / "supabase" / "migrations" / "088_rarity_potential_guards.sql"


def load(stem: str) -> str:
    matches = sorted(DUMP.glob(f"{stem}*"), key=lambda p: len(p.name), reverse=True)
    if not matches:
        raise FileNotFoundError(stem)
    return matches[0].read_text(encoding="utf-8").rstrip() + "\n\n"


HEADER = Path(__file__).with_name("_088_header.sql")
# inline header below

HEADER_SQL = r"""-- 088_rarity_potential_guards.sql
-- US-42.2 / US-42.7 / US-42.9 — rarity potential cap integrity (049)
-- Containment only. VALIDATE constraints in 089 after repair.

CREATE OR REPLACE FUNCTION public.rarity_potential_cap(p_rarity TEXT)
RETURNS INTEGER
LANGUAGE sql
IMMUTABLE
STRICT
AS $$
    SELECT CASE p_rarity
        WHEN 'Common' THEN 75
        WHEN 'Rare' THEN 85
        WHEN 'Epic' THEN 92
        WHEN 'Legendary' THEN 99
        ELSE NULL
    END;
$$;

CREATE OR REPLACE FUNCTION public.effective_card_potential(p_rarity TEXT, p_potential INTEGER)
RETURNS INTEGER
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT LEAST(p_potential, public.rarity_potential_cap(p_rarity));
$$;

CREATE OR REPLACE FUNCTION public.assert_card_potential_integrity(
    p_rarity TEXT,
    p_overall INTEGER,
    p_potential INTEGER,
    p_base_potential INTEGER
) RETURNS VOID
LANGUAGE plpgsql
IMMUTABLE
AS $$
DECLARE
    v_cap INTEGER := public.rarity_potential_cap(p_rarity);
BEGIN
    IF v_cap IS NULL THEN
        RAISE EXCEPTION 'Unsupported rarity: %', p_rarity;
    END IF;
    IF p_overall > v_cap THEN
        RAISE EXCEPTION 'OVR % exceeds rarity cap % for %', p_overall, v_cap, p_rarity;
    END IF;
    IF p_potential > v_cap THEN
        RAISE EXCEPTION 'POT % exceeds rarity cap % for %', p_potential, v_cap, p_rarity;
    END IF;
    IF p_base_potential IS NOT NULL AND p_base_potential > v_cap THEN
        RAISE EXCEPTION 'base POT % exceeds rarity cap % for %', p_base_potential, v_cap, p_rarity;
    END IF;
    IF p_overall > p_potential THEN
        RAISE EXCEPTION 'OVR % exceeds POT %', p_overall, p_potential;
    END IF;
END;
$$;

INSERT INTO public.game_config (key, value_json)
VALUES ('potential_rarity_caps_enabled', 'true'::jsonb)
ON CONFLICT (key) DO NOTHING;

CREATE TABLE IF NOT EXISTS public.potential_cap_repair_audit (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id TEXT NOT NULL,
    card_id UUID NOT NULL,
    owner_id BIGINT,
    rarity TEXT NOT NULL,
    old_overall INTEGER,
    new_overall INTEGER,
    old_potential INTEGER,
    new_potential INTEGER,
    old_base_potential INTEGER,
    new_base_potential INTEGER,
    old_stats JSONB,
    new_stats JSONB,
    refund_sp INTEGER NOT NULL DEFAULT 0,
    refund_coins BIGINT NOT NULL DEFAULT 0,
    refund_energy INTEGER NOT NULL DEFAULT 0,
    refund_other JSONB NOT NULL DEFAULT '{}'::jsonb,
    refund_confidence TEXT NOT NULL DEFAULT 'NONE'
        CHECK (refund_confidence IN ('EXACT', 'RECONSTRUCTED', 'MANUAL_REVIEW', 'NONE')),
    repair_category TEXT
        CHECK (repair_category IS NULL OR repair_category IN ('A', 'B', 'C')),
    repair_status TEXT NOT NULL DEFAULT 'dry_run',
    repaired_at TIMESTAMPTZ,
    notified_at TIMESTAMPTZ,
    notification_attempts INTEGER NOT NULL DEFAULT 0,
    notification_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (batch_id, card_id)
);

CREATE INDEX IF NOT EXISTS idx_potential_cap_repair_audit_owner
    ON public.potential_cap_repair_audit (owner_id);

ALTER TABLE public.potential_cap_repair_audit ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS potential_cap_repair_audit_select ON public.potential_cap_repair_audit;
CREATE POLICY potential_cap_repair_audit_select ON public.potential_cap_repair_audit
    FOR SELECT TO anon, authenticated, service_role USING (true);

DROP POLICY IF EXISTS potential_cap_repair_audit_insert ON public.potential_cap_repair_audit;
CREATE POLICY potential_cap_repair_audit_insert ON public.potential_cap_repair_audit
    FOR INSERT TO anon, authenticated, service_role WITH CHECK (true);

DROP POLICY IF EXISTS potential_cap_repair_audit_update ON public.potential_cap_repair_audit;
CREATE POLICY potential_cap_repair_audit_update ON public.potential_cap_repair_audit
    FOR UPDATE TO anon, authenticated, service_role USING (true) WITH CHECK (true);

GRANT SELECT, INSERT, UPDATE ON public.potential_cap_repair_audit
    TO anon, authenticated, service_role;

"""

FOOTER_SQL = r"""
ALTER TABLE public.player_cards
    DROP CONSTRAINT IF EXISTS player_cards_potential_rarity_cap_chk;
ALTER TABLE public.player_cards
    ADD CONSTRAINT player_cards_potential_rarity_cap_chk
    CHECK (
        public.rarity_potential_cap(rarity) IS NOT NULL
        AND potential <= public.rarity_potential_cap(rarity)
    ) NOT VALID;

ALTER TABLE public.player_cards
    DROP CONSTRAINT IF EXISTS player_cards_base_potential_rarity_cap_chk;
ALTER TABLE public.player_cards
    ADD CONSTRAINT player_cards_base_potential_rarity_cap_chk
    CHECK (
        public.rarity_potential_cap(rarity) IS NOT NULL
        AND (base_potential IS NULL OR base_potential <= public.rarity_potential_cap(rarity))
    ) NOT VALID;

ALTER TABLE public.player_cards
    DROP CONSTRAINT IF EXISTS player_cards_overall_potential_chk;
ALTER TABLE public.player_cards
    ADD CONSTRAINT player_cards_overall_potential_chk
    CHECK (overall <= potential) NOT VALID;

DO $$
DECLARE
    missing TEXT[];
BEGIN
    SELECT array_agg(req.obj ORDER BY req.obj)
    INTO missing
    FROM (
        VALUES
            ('function:rarity_potential_cap'),
            ('function:effective_card_potential'),
            ('function:assert_card_potential_integrity'),
            ('table:public.potential_cap_repair_audit'),
            ('policy:public.potential_cap_repair_audit.potential_cap_repair_audit_select'),
            ('policy:public.potential_cap_repair_audit.potential_cap_repair_audit_insert'),
            ('policy:public.potential_cap_repair_audit.potential_cap_repair_audit_update')
    ) AS req(obj)
    WHERE NOT (
        (req.obj LIKE 'table:%' AND to_regclass(split_part(req.obj, ':', 2)) IS NOT NULL)
        OR (
            req.obj LIKE 'policy:%'
            AND EXISTS (
                SELECT 1 FROM pg_policies pol
                WHERE pol.schemaname = split_part(split_part(req.obj, ':', 2), '.', 1)
                  AND pol.tablename = split_part(split_part(req.obj, ':', 2), '.', 2)
                  AND pol.policyname = split_part(split_part(req.obj, ':', 2), '.', 3)
            )
        )
        OR (
            req.obj LIKE 'function:%'
            AND CASE split_part(req.obj, ':', 2)
                WHEN 'rarity_potential_cap'
                    THEN to_regprocedure('public.rarity_potential_cap(text)')
                WHEN 'effective_card_potential'
                    THEN to_regprocedure('public.effective_card_potential(text,integer)')
                WHEN 'assert_card_potential_integrity'
                    THEN to_regprocedure('public.assert_card_potential_integrity(text,integer,integer,integer)')
                ELSE NULL
            END IS NOT NULL
        )
    );

    IF missing IS NOT NULL THEN
        RAISE EXCEPTION '088 rarity potential guards missing: %', missing;
    END IF;
END $$;
"""


def must_replace(sql: str, old: str, new: str, label: str) -> str:
    if old not in sql:
        raise RuntimeError(f"{label}: pattern not found:\n{old[:120]!r}")
    return sql.replace(old, new, 1)


def patch_process_match_result(sql: str) -> str:
    sql = must_replace(
        sql,
        "    v_new_pot INTEGER;\n    v_xp INTEGER;",
        "    v_new_pot INTEGER;\n    v_rarity TEXT;\n    v_xp INTEGER;",
        "match declare",
    )
    sql = must_replace(
        sql,
        "SELECT date_of_birth, potential, base_potential, recent_match_ratings\n"
        "        INTO v_dob, v_pot, v_init_pot, v_recent",
        "SELECT date_of_birth, potential, base_potential, recent_match_ratings, rarity\n"
        "        INTO v_dob, v_pot, v_init_pot, v_recent, v_rarity",
        "match select",
    )
    return must_replace(
        sql,
        "v_new_pot := LEAST(99, LEAST(v_pot + v_boost, v_init_pot + 10));",
        "v_new_pot := LEAST(\n"
        "                        public.rarity_potential_cap(v_rarity),\n"
        "                        v_pot + v_boost,\n"
        "                        v_init_pot + 10\n"
        "                    );",
        "match least",
    )


def patch_register(sql: str) -> str:
    return must_replace(
        sql,
        "        IF v_pot < v_card_record.overall THEN\n"
        "            v_pot := v_card_record.overall;\n"
        "        END IF;",
        "        PERFORM public.assert_card_potential_integrity(\n"
        "            v_card_record.rarity,\n"
        "            v_card_record.overall,\n"
        "            v_pot,\n"
        "            COALESCE(v_card_record.base_potential, v_pot)\n"
        "        );",
        "register",
    )


def patch_youth_intake(sql: str) -> str:
    return must_replace(
        sql,
        "        IF v_pot < v_card.overall THEN\n"
        "            v_pot := v_card.overall;\n"
        "        END IF;",
        "        PERFORM public.assert_card_potential_integrity(\n"
        "            v_card.rarity,\n"
        "            v_card.overall,\n"
        "            v_pot,\n"
        "            COALESCE(v_card.base_potential, v_pot)\n"
        "        );",
        "youth_intake",
    )


def patch_scout(sql: str) -> str:
    return must_replace(
        sql,
        "    IF v_pot < COALESCE((v_card->>'overall')::INT, 0) THEN\n"
        "        v_pot := (v_card->>'overall')::INT;\n"
        "    END IF;",
        "    PERFORM public.assert_card_potential_integrity(\n"
        "        COALESCE(v_card->>'rarity', 'Common'),\n"
        "        COALESCE((v_card->>'overall')::INT, 0),\n"
        "        v_pot,\n"
        "        COALESCE((v_card->>'base_potential')::INT, v_pot)\n"
        "    );",
        "scout",
    )


def patch_claim_pack(sql: str) -> str:
    return must_replace(
        sql,
        "        INSERT INTO public.player_cards (",
        "        PERFORM public.assert_card_potential_integrity(\n"
        "            v_card.rarity,\n"
        "            v_card.overall,\n"
        "            COALESCE(v_card.potential, v_card.base_potential, v_card.overall),\n"
        "            COALESCE(v_card.base_potential, v_card.potential, v_card.overall)\n"
        "        );\n\n"
        "        INSERT INTO public.player_cards (",
        "claim_pack",
    )


def patch_allocate(sql: str) -> str:
    sql = must_replace(
        sql,
        "    v_potential INTEGER;\n    v_alloc_count INTEGER;",
        "    v_potential INTEGER;\n    v_rarity TEXT;\n    v_alloc_count INTEGER;",
        "alloc declare",
    )
    sql = must_replace(
        sql,
        "        'SELECT skill_points, overall, potential, %I, daily_alloc_count, alloc_reset_date '\n"
        "        || 'FROM public.player_cards WHERE id = $1 AND owner_id = $2 FOR UPDATE',\n"
        "        v_col\n"
        "    ) INTO v_points, v_overall, v_potential, v_current, v_alloc_count, v_alloc_reset",
        "        'SELECT skill_points, overall, potential, rarity, %I, daily_alloc_count, alloc_reset_date '\n"
        "        || 'FROM public.player_cards WHERE id = $1 AND owner_id = $2 FOR UPDATE',\n"
        "        v_col\n"
        "    ) INTO v_points, v_overall, v_potential, v_rarity, v_current, v_alloc_count, v_alloc_reset",
        "alloc select",
    )
    return must_replace(
        sql,
        "    IF v_overall >= v_potential THEN\n"
        "        RAISE EXCEPTION 'Player is already at maximum overall for their potential';",
        "    v_potential := public.effective_card_potential(v_rarity, v_potential);\n\n"
        "    IF v_overall >= v_potential THEN\n"
        "        RAISE EXCEPTION 'Player is already at maximum overall for their potential';",
        "alloc gate",
    )


def patch_drill(sql: str) -> str:
    sql = must_replace(
        sql,
        "    v_potential INTEGER;\n    v_boost_eligible BOOLEAN := FALSE;",
        "    v_potential INTEGER;\n    v_rarity TEXT;\n    v_boost_eligible BOOLEAN := FALSE;",
        "drill declare",
    )
    sql = must_replace(
        sql,
        "        'SELECT overall, level, date_of_birth, potential, %I '\n"
        "        || 'FROM public.player_cards WHERE id = $1 FOR UPDATE',\n"
        "        v_stat_col\n"
        "    ) INTO v_ovr, v_card_level, v_dob, v_potential, v_stat_val",
        "        'SELECT overall, level, date_of_birth, potential, rarity, %I '\n"
        "        || 'FROM public.player_cards WHERE id = $1 FOR UPDATE',\n"
        "        v_stat_col\n"
        "    ) INTO v_ovr, v_card_level, v_dob, v_potential, v_rarity, v_stat_val",
        "drill select",
    )
    return must_replace(
        sql,
        "    -- Soft-fail boost eligibility (do not RAISE — XP/costs still apply)\n"
        "    IF v_stat_val >= 99 THEN",
        "    v_potential := public.effective_card_potential(v_rarity, v_potential);\n\n"
        "    -- Soft-fail boost eligibility (do not RAISE — XP/costs still apply)\n"
        "    IF v_stat_val >= 99 THEN",
        "drill gate",
    )


def patch_evolution(sql: str) -> str:
    sql = must_replace(
        sql,
        "    v_potential INTEGER;\nBEGIN",
        "    v_potential INTEGER;\n    v_rarity TEXT;\nBEGIN",
        "evo declare",
    )
    sql = must_replace(
        sql,
        "    SELECT overall, potential\n"
        "    INTO v_overall, v_potential\n"
        "    FROM public.player_cards\n"
        "    WHERE id = v_card_id\n"
        "    FOR UPDATE;",
        "    SELECT overall, potential, rarity\n"
        "    INTO v_overall, v_potential, v_rarity\n"
        "    FROM public.player_cards\n"
        "    WHERE id = v_card_id\n"
        "    FOR UPDATE;\n\n"
        "    v_potential := public.effective_card_potential(v_rarity, v_potential);",
        "evo select",
    )
    return sql


def patch_evo_steps(sql: str) -> str:
    sql = must_replace(
        sql,
        "    v_potential INTEGER;\n    v_steps INTEGER := 0;",
        "    v_potential INTEGER;\n    v_rarity TEXT;\n    v_steps INTEGER := 0;",
        "evo_steps declare",
    )
    return must_replace(
        sql,
        "        'SELECT %I, overall, potential FROM public.player_cards WHERE id = $1',\n"
        "        p_stat_col\n"
        "    ) INTO v_current, v_overall, v_potential USING p_card_id;\n\n"
        "    IF v_current IS NULL THEN\n"
        "        RETURN 0;\n"
        "    END IF;",
        "        'SELECT %I, overall, potential, rarity FROM public.player_cards WHERE id = $1',\n"
        "        p_stat_col\n"
        "    ) INTO v_current, v_overall, v_potential, v_rarity USING p_card_id;\n\n"
        "    IF v_current IS NULL THEN\n"
        "        RETURN 0;\n"
        "    END IF;\n"
        "    v_potential := public.effective_card_potential(v_rarity, v_potential);",
        "evo_steps select",
    )


def patch_academy(sql: str) -> str:
    return must_replace(
        sql,
        "v_pot := GREATEST(v_card.overall, COALESCE(v_card.potential, v_card.overall));",
        "v_pot := public.effective_card_potential(\n"
        "            v_card.rarity,\n"
        "            GREATEST(v_card.overall, COALESCE(v_card.potential, v_card.overall))\n"
        "        );",
        "academy",
    )


def patch_fodder(sql: str) -> str:
    return must_replace(
        sql,
        "    SELECT owner_id, overall, potential\n"
        "    INTO v_target_owner, v_target_overall, v_target_potential\n"
        "    FROM public.player_cards\n"
        "    WHERE id = p_target_id\n"
        "    FOR UPDATE;\n\n"
        "    IF v_target_owner IS NULL OR v_target_owner != p_owner_id THEN",
        "    SELECT owner_id, overall, potential, rarity\n"
        "    INTO v_target_owner, v_target_overall, v_target_potential, v_target_rarity\n"
        "    FROM public.player_cards\n"
        "    WHERE id = p_target_id\n"
        "    FOR UPDATE;\n\n"
        "    IF v_target_owner IS NULL OR v_target_owner != p_owner_id THEN",
        "fodder select",
    ).replace(
        # declare — best effort
        "    v_target_potential INTEGER;",
        "    v_target_potential INTEGER;\n    v_target_rarity TEXT;",
        1,
    )


def _finish_fodder(sql: str) -> str:
    if "v_target_rarity TEXT;" not in sql:
        # try alternate declare style
        pass
    return must_replace(
        sql,
        "    IF v_target_owner IS NULL OR v_target_owner != p_owner_id THEN\n"
        "        RAISE EXCEPTION 'Target player card not found or not owned by you';\n"
        "    END IF;",
        "    IF v_target_owner IS NULL OR v_target_owner != p_owner_id THEN\n"
        "        RAISE EXCEPTION 'Target player card not found or not owned by you';\n"
        "    END IF;\n\n"
        "    PERFORM public.assert_card_potential_integrity(\n"
        "        v_target_rarity, v_target_overall, v_target_potential, NULL\n"
        "    );",
        "fodder assert",
    )


def patch_mentor(sql: str) -> str:
    return must_replace(
        sql,
        "    SELECT * INTO v_tgt FROM public.player_cards WHERE id = p_target_card_id;\n"
        "    IF NOT FOUND OR v_tgt.owner_id IS DISTINCT FROM p_owner_id THEN\n"
        "        RAISE EXCEPTION 'Target card not found or not owned';\n"
        "    END IF;\n\n"
        "    IF COALESCE(v_src.overall, 0) < COALESCE(v_src.potential, 0) THEN",
        "    SELECT * INTO v_tgt FROM public.player_cards WHERE id = p_target_card_id;\n"
        "    IF NOT FOUND OR v_tgt.owner_id IS DISTINCT FROM p_owner_id THEN\n"
        "        RAISE EXCEPTION 'Target card not found or not owned';\n"
        "    END IF;\n\n"
        "    PERFORM public.assert_card_potential_integrity(\n"
        "        v_src.rarity, v_src.overall, v_src.potential, v_src.base_potential\n"
        "    );\n"
        "    PERFORM public.assert_card_potential_integrity(\n"
        "        v_tgt.rarity, v_tgt.overall, v_tgt.potential, v_tgt.base_potential\n"
        "    );\n\n"
        "    IF COALESCE(v_src.overall, 0) < public.effective_card_potential(v_src.rarity, v_src.potential) THEN",
        "mentor",
    ).replace(
        "    IF COALESCE(v_tgt.overall, 0) >= COALESCE(v_tgt.potential, 0) THEN",
        "    IF COALESCE(v_tgt.overall, 0) >= public.effective_card_potential(v_tgt.rarity, v_tgt.potential) THEN",
        1,
    )


def main() -> None:
    parts: list[str] = [HEADER_SQL]
    steps = [
        ("process_match_result", patch_process_match_result),
        ("register_new_player", patch_register),
        ("process_youth_intake", patch_youth_intake),
        ("sign_youth_scout_prospect", patch_scout),
        ("claim_daily_pack", patch_claim_pack),
        ("allocate_skill_point", patch_allocate),
        ("process_stat_drill", patch_drill),
        ("claim_evolution_reward", patch_evolution),
        ("evolution_stat_reward_steps", patch_evo_steps),
        ("process_daily_academy_growth", patch_academy),
        ("train_with_fodder", lambda s: _finish_fodder(patch_fodder(s))),
        ("transfer_mentor_xp", patch_mentor),
    ]
    for name, fn in steps:
        body = load(name)
        parts.append(fn(body))
        print("ok", name)
    parts.append(FOOTER_SQL)
    OUT.write_text("".join(parts), encoding="utf-8")
    print("wrote", OUT, OUT.stat().st_size)


if __name__ == "__main__":
    main()
