CREATE OR REPLACE FUNCTION public.process_daily_academy_growth()
 RETURNS jsonb
 LANGUAGE plpgsql
AS $function$
DECLARE
    v_card RECORD;
    v_level INTEGER;
    v_points INTEGER;
    v_prog INTEGER;
    v_ovr INTEGER;
    v_pot INTEGER;
    v_gained INTEGER;
    v_bump RECORD;
    v_age INTEGER;
    v_age_out INTEGER;
    v_ready INTEGER;
    v_ticked INTEGER := 0;
    v_promoted JSONB := '[]'::JSONB;
    v_released JSONB := '[]'::JSONB;
    v_promo JSONB;
BEGIN
    v_age_out := public.get_game_config_int('academy_age_out', 20)::INTEGER;
    v_ready := public.get_game_config_int('academy_ready_ovr', 65)::INTEGER;

    FOR v_card IN
        SELECT pc.*, p.youth_academy_level
        FROM public.player_cards pc
        JOIN public.players p ON p.discord_id = pc.owner_id
        WHERE pc.in_academy = TRUE
          AND COALESCE(pc.is_retired, FALSE) = FALSE
          AND COALESCE(p.is_ai, FALSE) = FALSE
        FOR UPDATE OF pc
    LOOP
        v_level := COALESCE(v_card.youth_academy_level, 1);
        v_pot := GREATEST(v_card.overall, COALESCE(v_card.potential, v_card.overall));
        v_ovr := LEAST(v_card.overall, v_pot);
        v_prog := COALESCE(v_card.academy_progress, 0);
        v_points := public.academy_daily_points(v_level, v_pot);
        v_prog := v_prog + v_points;
        v_gained := 0;

        WHILE v_prog >= 100 AND v_ovr < v_pot LOOP
            v_ovr := v_ovr + 1;
            v_prog := v_prog - 100;
            v_gained := v_gained + 1;
            SELECT * INTO v_bump FROM public.academy_bump_primary_stat(
                v_card.position, v_card.pac, v_card.sho, v_card.pas, v_card.dri, v_card."def", v_card.phy, v_pot
            );
            v_card.pac := v_bump.pac;
            v_card.sho := v_bump.sho;
            v_card.pas := v_bump.pas;
            v_card.dri := v_bump.dri;
            v_card."def" := v_bump."def";
            v_card.phy := v_bump.phy;
        END LOOP;

        UPDATE public.player_cards
        SET overall = v_ovr,
            academy_progress = v_prog,
            pac = v_card.pac,
            sho = v_card.sho,
            pas = v_card.pas,
            dri = v_card.dri,
            "def" = v_card."def",
            phy = v_card.phy,
            age = public.card_age_from_dob(date_of_birth)
        WHERE id = v_card.id;

        v_ticked := v_ticked + 1;

        v_age := public.card_age_from_dob(v_card.date_of_birth);
        IF v_age >= v_age_out THEN
            BEGIN
                v_promo := public.promote_academy_player(v_card.owner_id, v_card.id);
                v_promoted := v_promoted || jsonb_build_array(jsonb_build_object(
                    'owner_id', v_card.owner_id,
                    'card_id', v_card.id,
                    'name', v_card.name,
                    'result', 'promoted',
                    'early_promote', v_promo->>'early_promote'
                ));
            EXCEPTION WHEN OTHERS THEN
                PERFORM public.release_academy_player(v_card.owner_id, v_card.id);
                v_released := v_released || jsonb_build_array(jsonb_build_object(
                    'owner_id', v_card.owner_id,
                    'card_id', v_card.id,
                    'name', v_card.name,
                    'result', 'released',
                    'reason', SQLERRM
                ));
            END;
        END IF;
    END LOOP;

    RETURN jsonb_build_object(
        'ticked', v_ticked,
        'age_out_promoted', v_promoted,
        'age_out_released', v_released,
        'ready_ovr', v_ready
    );
END;
$function$
