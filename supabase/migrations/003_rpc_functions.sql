-- supabase/migrations/003_rpc_functions.sql

CREATE OR REPLACE FUNCTION regen_energy_tick() RETURNS VOID AS $$
BEGIN
    UPDATE players
    SET energy = LEAST(energy + 2, max_energy)
    WHERE energy < max_energy;
END;
$$ LANGUAGE plpgsql;
