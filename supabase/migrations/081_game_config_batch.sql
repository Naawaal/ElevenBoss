-- US-43: batch game_config fetch for hub cold loads (one RT for many keys)

CREATE OR REPLACE FUNCTION public.get_game_config_many(p_keys TEXT[])
RETURNS JSONB
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_out JSONB := '{}'::JSONB;
    v_key TEXT;
    v_val JSONB;
BEGIN
    IF p_keys IS NULL OR array_length(p_keys, 1) IS NULL THEN
        RETURN v_out;
    END IF;
    FOREACH v_key IN ARRAY p_keys
    LOOP
        SELECT value_json INTO v_val FROM public.game_config WHERE key = v_key;
        v_out := v_out || jsonb_build_object(v_key, v_val);
    END LOOP;
    RETURN v_out;
END;
$$;

DO $$
BEGIN
  IF to_regprocedure('public.get_game_config_many(text[])') IS NULL THEN
    RAISE EXCEPTION '081 guard failed: get_game_config_many(text[]) missing';
  END IF;
END $$;
