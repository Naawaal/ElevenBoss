-- 097_academy_season_aging_decay.sql
-- US-6 / FR-017: unpromoted academy prospects may lose ≤1 POT at season aging.
-- Forward fix for Feature 052 acceptance (051 gap).

BEGIN;

CREATE OR REPLACE FUNCTION public.process_season_aging()
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_card RECORD;
    v_new_age INTEGER;
    v_old_age INTEGER;
    v_years INTEGER;
    v_i INTEGER;
    v_age_i INTEGER;
    v_retire_age INTEGER;
    v_warn_age INTEGER;
    v_retired INTEGER := 0;
    v_declined INTEGER := 0;
    v_warned INTEGER := 0;
    v_pac INTEGER;
    v_phy INTEGER;
    v_pas INTEGER;
    v_def INTEGER;
    v_dri INTEGER;
    v_sho INTEGER;
    v_academy_warn INTEGER;
    v_decay_max INTEGER;
    v_cap INTEGER;
    v_new_pot INTEGER;
    v_academy_decayed INTEGER := 0;
    v_academy_warned INTEGER := 0;
BEGIN
    v_retire_age := public.get_game_config_int('retirement_age', 36)::INTEGER;
    v_warn_age := public.get_game_config_int('retirement_warning_age', 35)::INTEGER;
    v_academy_warn := public.get_game_config_int('academy_age_warn', 20)::INTEGER;
    v_decay_max := public.get_game_config_int('academy_aging_decay_max', 1)::INTEGER;

    FOR v_card IN
        SELECT id, owner_id, age, date_of_birth, pac, phy, pas, def, dri, sho,
               retirement_notified_at, is_retired, in_academy, potential, overall,
               rarity, academy_warned_aging_at
        FROM public.player_cards
        WHERE COALESCE(is_retired, FALSE) = FALSE
        FOR UPDATE
    LOOP
        v_new_age := public.card_age_from_dob(v_card.date_of_birth);
        v_old_age := COALESCE(v_card.age, v_new_age);

        UPDATE public.player_cards SET age = v_new_age WHERE id = v_card.id;

        IF v_new_age >= v_warn_age AND v_card.retirement_notified_at IS NULL THEN
            UPDATE public.player_cards
            SET retirement_notified_at = NOW()
            WHERE id = v_card.id;
            v_warned := v_warned + 1;
        END IF;

        -- Academy aging warning + bounded POT decay (unpromoted only)
        IF COALESCE(v_card.in_academy, FALSE)
           AND v_new_age >= v_academy_warn THEN
            IF v_card.academy_warned_aging_at IS NULL THEN
                UPDATE public.player_cards
                SET academy_warned_aging_at = NOW()
                WHERE id = v_card.id;
                v_academy_warned := v_academy_warned + 1;
            END IF;
            IF v_new_age > v_old_age THEN
                v_cap := public.rarity_potential_cap(v_card.rarity);
                IF v_cap IS NOT NULL THEN
                    v_new_pot := GREATEST(
                        v_card.overall,
                        LEAST(
                            v_cap,
                            v_card.potential
                            - LEAST(
                                v_decay_max,
                                GREATEST(0, v_card.potential - v_card.overall)
                              )
                        )
                    );
                    IF v_new_pot < v_card.potential THEN
                        UPDATE public.player_cards
                        SET potential = v_new_pot,
                            base_potential = LEAST(COALESCE(base_potential, v_new_pot), v_new_pot),
                            pot_visible_hi = CASE
                                WHEN pot_visible_hi IS NULL THEN NULL
                                ELSE GREATEST(COALESCE(pot_visible_lo, v_new_pot), LEAST(pot_visible_hi, v_new_pot))
                            END,
                            pot_visible_lo = CASE
                                WHEN pot_visible_lo IS NULL THEN NULL
                                ELSE LEAST(pot_visible_lo, v_new_pot)
                            END
                        WHERE id = v_card.id;
                        v_academy_decayed := v_academy_decayed + 1;
                        v_card.potential := v_new_pot;
                    END IF;
                END IF;
            END IF;
        END IF;

        IF v_new_age > v_old_age THEN
            v_years := v_new_age - v_old_age;
            FOR v_i IN 1..v_years LOOP
                v_age_i := v_old_age + v_i;
                IF v_age_i >= 31 THEN
                    v_pac := GREATEST(1, v_card.pac - CASE WHEN v_age_i >= 35 THEN 2 ELSE 1 END);
                    v_phy := GREATEST(1, v_card.phy - CASE WHEN v_age_i >= 35 THEN 2 ELSE 1 END);
                    v_pas := v_card.pas;
                    v_def := v_card.def;
                    v_dri := v_card.dri;
                    v_sho := v_card.sho;
                    IF v_age_i >= 33 THEN
                        v_pas := GREATEST(1, v_card.pas - 1);
                        v_def := GREATEST(1, v_card.def - 1);
                        v_dri := GREATEST(1, v_card.dri - 1);
                    END IF;
                    IF v_age_i >= 35 THEN
                        v_sho := GREATEST(1, v_card.sho - 1);
                    END IF;
                    UPDATE public.player_cards
                    SET pac = v_pac, phy = v_phy, pas = v_pas, def = v_def,
                        dri = v_dri, sho = v_sho
                    WHERE id = v_card.id;
                    PERFORM public.recalculate_card_ovr(v_card.id);
                    v_declined := v_declined + 1;
                    SELECT pac, phy, pas, def, dri, sho
                    INTO v_card.pac, v_card.phy, v_card.pas, v_card.def, v_card.dri, v_card.sho
                    FROM public.player_cards WHERE id = v_card.id;
                END IF;
            END LOOP;
        END IF;

        IF v_new_age >= v_retire_age THEN
            PERFORM public.retire_player_card(v_card.id);
            v_retired := v_retired + 1;
        END IF;
    END LOOP;

    RETURN jsonb_build_object(
        'declined_cards', v_declined,
        'retired_cards', v_retired,
        'warned_cards', v_warned,
        'academy_decayed', v_academy_decayed,
        'academy_warned', v_academy_warned
    );
END;
$$;

GRANT ALL PRIVILEGES ON FUNCTION public.process_season_aging()
    TO anon, authenticated, service_role;

COMMIT;
