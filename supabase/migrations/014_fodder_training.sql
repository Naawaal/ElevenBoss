-- supabase/migrations/014_fodder_training.sql

-- Create RPC train_with_fodder
CREATE OR REPLACE FUNCTION public.train_with_fodder(
    p_owner_id BIGINT,
    p_target_id UUID,
    p_fodder_id UUID
) RETURNS BOOLEAN AS $$
DECLARE
    v_target_owner BIGINT;
    v_fodder_owner BIGINT;
    v_target_level INTEGER;
    v_target_base_rating INTEGER;
    v_target_rarity TEXT;
    v_target_overall INTEGER;
    v_target_cap INTEGER;
    v_new_overall INTEGER;
BEGIN
    -- 1. Verify ownership of target card
    SELECT owner_id, level, base_rating, rarity, overall 
    INTO v_target_owner, v_target_level, v_target_base_rating, v_target_rarity, v_target_overall
    FROM public.player_cards
    WHERE id = p_target_id;
    
    IF v_target_owner IS NULL OR v_target_owner != p_owner_id THEN
        RAISE EXCEPTION 'Target player card not found or not owned by you';
    END IF;
    
    -- 2. Verify ownership of fodder card
    SELECT owner_id INTO v_fodder_owner
    FROM public.player_cards
    WHERE id = p_fodder_id;
    
    IF v_fodder_owner IS NULL OR v_fodder_owner != p_owner_id THEN
        RAISE EXCEPTION 'Fodder player card not found or not owned by you';
    END IF;

    -- 3. Prevent using the same card for target and fodder
    IF p_target_id = p_fodder_id THEN
        RAISE EXCEPTION 'Cannot use the same card as both target and fodder';
    END IF;

    -- 4. Check if fodder is assigned to starting 11
    IF EXISTS (
        SELECT 1 FROM public.squad_assignments
        WHERE player_card_id = p_fodder_id
    ) THEN
        RAISE EXCEPTION 'Cannot burn a player card that is currently in your starting 11';
    END IF;

    -- Check if fodder is in active training
    IF EXISTS (
        SELECT 1 FROM public.active_training
        WHERE card_id = p_fodder_id AND end_time > NOW()
    ) THEN
        RAISE EXCEPTION 'Cannot burn a player card that is currently in active training';
    END IF;

    -- Check if fodder is in active evolutions
    IF EXISTS (
        SELECT 1 FROM public.active_evolutions
        WHERE card_id = p_fodder_id
    ) THEN
        RAISE EXCEPTION 'Cannot burn a player card that is currently in an active evolution';
    END IF;
    
    -- 5. Check if target is already at its rarity cap
    IF v_target_rarity = 'Common' THEN
        v_target_cap := 75;
    ELSIF v_target_rarity = 'Rare' THEN
        v_target_cap := 84;
    ELSIF v_target_rarity = 'Epic' THEN
        v_target_cap := 90;
    ELSE
        v_target_cap := 99; -- Legendary or fallback
    END IF;
    
    IF v_target_overall >= v_target_cap THEN
        RAISE EXCEPTION 'Target player is already at the maximum overall rating for their rarity';
    END IF;
    
    -- 6. Delete the fodder card (Cascade takes care of squad assignments if any)
    DELETE FROM public.player_cards
    WHERE id = p_fodder_id;
    
    -- 7. Increment target level and recalculate overall
    v_target_level := v_target_level + 1;
    v_new_overall := LEAST(v_target_base_rating + (v_target_level - 1), v_target_cap);
    
    UPDATE public.player_cards
    SET level = v_target_level,
        overall = v_new_overall
    WHERE id = p_target_id;
    
    -- Log the training event in player_xp_log
    INSERT INTO public.player_xp_log (card_id, xp_amount, source)
    VALUES (p_target_id, 100, 'fodder_training');
    
    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

-- Grant privileges to Supabase roles
GRANT ALL PRIVILEGES ON FUNCTION public.train_with_fodder TO anon, authenticated, service_role;
