-- supabase/migrations/003_player_lifecycle.sql

-- 1. Alter player_cards table to add new progression columns
ALTER TABLE public.player_cards ADD COLUMN IF NOT EXISTS role TEXT DEFAULT 'Balanced';
ALTER TABLE public.player_cards ADD COLUMN IF NOT EXISTS morale INTEGER DEFAULT 80 CHECK (morale >= 0 AND morale <= 100);
ALTER TABLE public.player_cards ADD COLUMN IF NOT EXISTS contract_expires_at TIMESTAMPTZ DEFAULT (NOW() + INTERVAL '7 days');
ALTER TABLE public.player_cards ADD COLUMN IF NOT EXISTS potential INTEGER DEFAULT 85 CHECK (potential >= 1 AND potential <= 99);
ALTER TABLE public.player_cards ADD COLUMN IF NOT EXISTS age INTEGER DEFAULT 25 CHECK (age >= 15 AND age <= 45);

ALTER TABLE public.player_cards ADD COLUMN IF NOT EXISTS pac INTEGER DEFAULT 50 CHECK (pac >= 0 AND pac <= 99);
ALTER TABLE public.player_cards ADD COLUMN IF NOT EXISTS sho INTEGER DEFAULT 50 CHECK (sho >= 0 AND sho <= 99);
ALTER TABLE public.player_cards ADD COLUMN IF NOT EXISTS pas INTEGER DEFAULT 50 CHECK (pas >= 0 AND pas <= 99);
ALTER TABLE public.player_cards ADD COLUMN IF NOT EXISTS dri INTEGER DEFAULT 50 CHECK (dri >= 0 AND dri <= 99);
ALTER TABLE public.player_cards ADD COLUMN IF NOT EXISTS def INTEGER DEFAULT 50 CHECK (def >= 0 AND def <= 99);
ALTER TABLE public.player_cards ADD COLUMN IF NOT EXISTS phy INTEGER DEFAULT 50 CHECK (phy >= 0 AND phy <= 99);
ALTER TABLE public.player_cards ADD COLUMN IF NOT EXISTS skill_points INTEGER DEFAULT 0 CHECK (skill_points >= 0);

-- 2. Create the player_playstyles table
CREATE TABLE IF NOT EXISTS public.player_playstyles (
    card_id        UUID NOT NULL REFERENCES public.player_cards(id) ON DELETE CASCADE,
    playstyle_key  TEXT NOT NULL,
    PRIMARY KEY (card_id, playstyle_key)
);

-- 3. Create the active_evolutions table
CREATE TABLE IF NOT EXISTS public.active_evolutions (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    card_id           UUID NOT NULL REFERENCES public.player_cards(id) ON DELETE CASCADE,
    evolution_id      TEXT NOT NULL,
    target_metric     TEXT NOT NULL,
    current_progress  INTEGER NOT NULL DEFAULT 0,
    target_goal       INTEGER NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 4. Create the player_xp_log table
CREATE TABLE IF NOT EXISTS public.player_xp_log (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    card_id     UUID NOT NULL REFERENCES public.player_cards(id) ON DELETE CASCADE,
    xp_amount   INTEGER NOT NULL,
    source      TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 5. Create RPC process_match_result
CREATE OR REPLACE FUNCTION public.process_match_result(
    p_result TEXT,
    p_card_ids UUID[],
    p_xp_amount INTEGER
) RETURNS BOOLEAN AS $$
DECLARE
    v_card_id UUID;
    v_morale_delta INTEGER;
BEGIN
    -- Determine morale delta based on match result
    IF p_result = 'win' THEN
        v_morale_delta := 5;
    ELSIF p_result = 'draw' THEN
        v_morale_delta := 1;
    ELSE
        v_morale_delta := -5;
    END IF;

    FOREACH v_card_id IN ARRAY p_card_ids LOOP
        -- 1. Distribute XP and adjust morale
        UPDATE public.player_cards
        SET xp = xp + p_xp_amount,
            morale = LEAST(100, GREATEST(10, morale + v_morale_delta))
        WHERE id = v_card_id;

        -- 2. Log to player_xp_log
        INSERT INTO public.player_xp_log (card_id, xp_amount, source)
        VALUES (v_card_id, p_xp_amount, 'match_simulation');

        -- 3. Increment active evolution progress (if any is active for this card and the objective is 'matches')
        UPDATE public.active_evolutions
        SET current_progress = LEAST(target_goal, current_progress + 1)
        WHERE card_id = v_card_id AND target_metric = 'matches';
    END LOOP;

    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

-- 6. Create RPC renew_contract
CREATE OR REPLACE FUNCTION public.renew_contract(
    p_club_id BIGINT,
    p_card_id UUID,
    p_cost BIGINT,
    p_extension_days INTEGER
) RETURNS BOOLEAN AS $$
DECLARE
    v_coins BIGINT;
    v_expiry TIMESTAMPTZ;
BEGIN
    -- Check ownership
    IF NOT EXISTS (
        SELECT 1 FROM public.player_cards
        WHERE id = p_card_id AND owner_id = p_club_id
    ) THEN
        RAISE EXCEPTION 'Player card not found or not owned';
    END IF;

    -- Check coins
    SELECT coins INTO v_coins
    FROM public.players
    WHERE discord_id = p_club_id;

    IF v_coins < p_cost THEN
        RAISE EXCEPTION 'Insufficient coins';
    END IF;

    -- Deduct coins
    UPDATE public.players
    SET coins = coins - p_cost
    WHERE discord_id = p_club_id;

    -- Log ledger transaction
    INSERT INTO public.economy_ledger (club_id, amount, currency, source)
    VALUES (p_club_id, -p_cost, 'coins', 'contract_renewal');

    -- Get current expiry
    SELECT contract_expires_at INTO v_expiry
    FROM public.player_cards
    WHERE id = p_card_id;

    -- If already expired or null, start from NOW
    IF v_expiry IS NULL OR v_expiry < NOW() THEN
        v_expiry := NOW();
    END IF;

    -- Extend contract
    UPDATE public.player_cards
    SET contract_expires_at = v_expiry + (p_extension_days * INTERVAL '1 day')
    WHERE id = p_card_id;

    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

-- 7. Grant privileges to Supabase roles
GRANT ALL PRIVILEGES ON TABLE public.player_playstyles TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON TABLE public.active_evolutions TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON TABLE public.player_xp_log TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.process_match_result TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.renew_contract TO anon, authenticated, service_role;
