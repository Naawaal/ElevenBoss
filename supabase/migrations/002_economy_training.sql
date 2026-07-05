-- supabase/migrations/002_economy_training.sql

-- 1. Extend the players table
ALTER TABLE public.players ADD COLUMN IF NOT EXISTS tokens INTEGER DEFAULT 0 CHECK (tokens >= 0);
ALTER TABLE public.players ADD COLUMN IF NOT EXISTS training_slots_max INTEGER DEFAULT 2 CHECK (training_slots_max >= 1);
ALTER TABLE public.players ALTER COLUMN coins TYPE BIGINT;
ALTER TABLE public.players ALTER COLUMN coins SET DEFAULT 1000;

ALTER TABLE public.player_cards ADD COLUMN IF NOT EXISTS xp INTEGER DEFAULT 0 CHECK (xp >= 0);

-- 2. Create the economy_ledger table
CREATE TABLE IF NOT EXISTS public.economy_ledger (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    club_id     BIGINT NOT NULL REFERENCES public.players(discord_id) ON DELETE CASCADE,
    amount      BIGINT NOT NULL,
    currency    TEXT NOT NULL CHECK (currency IN ('coins', 'tokens')),
    source      TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. Create the active_training table
CREATE TABLE IF NOT EXISTS public.active_training (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    club_id     BIGINT NOT NULL REFERENCES public.players(discord_id) ON DELETE CASCADE,
    card_id     UUID NOT NULL REFERENCES public.player_cards(id) ON DELETE CASCADE,
    drill_type  TEXT NOT NULL CHECK (drill_type IN ('cardio', 'tactics', 'match_prep')),
    end_time    TIMESTAMPTZ NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 4. Create RPC process_training_start
CREATE OR REPLACE FUNCTION public.process_training_start(
    p_club_id BIGINT,
    p_card_id UUID,
    p_drill TEXT,
    p_cost BIGINT,
    p_duration_hours NUMERIC
) RETURNS BOOLEAN AS $$
DECLARE
    v_active_drills INTEGER;
    v_slots_max INTEGER;
    v_coins BIGINT;
BEGIN
    -- Get current coins and max training slots
    SELECT coins, training_slots_max INTO v_coins, v_slots_max
    FROM public.players
    WHERE discord_id = p_club_id;
    
    IF v_coins IS NULL THEN
        RAISE EXCEPTION 'Club/Player not found';
    END IF;
    
    -- Check card ownership
    IF NOT EXISTS (
        SELECT 1 FROM public.player_cards
        WHERE id = p_card_id AND owner_id = p_club_id
    ) THEN
        RAISE EXCEPTION 'Player card not found or not owned';
    END IF;

    -- Check if card is currently in training
    IF EXISTS (
        SELECT 1 FROM public.active_training
        WHERE card_id = p_card_id AND end_time > NOW()
    ) THEN
        RAISE EXCEPTION 'Player card is already in active training';
    END IF;

    -- Count active training drills
    SELECT COUNT(*) INTO v_active_drills
    FROM public.active_training
    WHERE club_id = p_club_id AND end_time > NOW();
    
    IF v_active_drills >= v_slots_max THEN
        RAISE EXCEPTION 'No training slots available';
    END IF;
    
    IF v_coins < p_cost THEN
        RAISE EXCEPTION 'Insufficient coins';
    END IF;
    
    -- Deduct coins
    UPDATE public.players
    SET coins = coins - p_cost
    WHERE discord_id = p_club_id;
    
    -- Log transaction
    INSERT INTO public.economy_ledger (club_id, amount, currency, source)
    VALUES (p_club_id, -p_cost, 'coins', 'training_drill_' || p_drill);
    
    -- Insert training drill
    INSERT INTO public.active_training (club_id, card_id, drill_type, end_time)
    VALUES (p_club_id, p_card_id, p_drill, NOW() + (p_duration_hours * INTERVAL '1 hour'));
    
    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

-- 5. Create RPC process_agent_sale
CREATE OR REPLACE FUNCTION public.process_agent_sale(
    p_club_id BIGINT,
    p_card_id UUID,
    p_sale_value BIGINT
) RETURNS BOOLEAN AS $$
DECLARE
    v_card_exists BOOLEAN;
BEGIN
    -- Verify ownership
    SELECT EXISTS (
        SELECT 1 FROM public.player_cards
        WHERE id = p_card_id AND owner_id = p_club_id
    ) INTO v_card_exists;
    
    IF NOT v_card_exists THEN
        RAISE EXCEPTION 'Player card not found or not owned';
    END IF;
    
    -- Delete card (Cascade takes care of squad assignments)
    DELETE FROM public.player_cards
    WHERE id = p_card_id;
    
    -- Add coins to club
    UPDATE public.players
    SET coins = coins + p_sale_value
    WHERE discord_id = p_club_id;
    
    -- Log transaction
    INSERT INTO public.economy_ledger (club_id, amount, currency, source)
    VALUES (p_club_id, p_sale_value, 'coins', 'agent_sale');
    
    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

-- 6. Grant privileges to Supabase roles
GRANT ALL PRIVILEGES ON TABLE public.economy_ledger TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON TABLE public.active_training TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.process_training_start TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.process_agent_sale TO anon, authenticated, service_role;
