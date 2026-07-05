# apps/discord_bot/db/client.py
from __future__ import annotations
import os
from dotenv import load_dotenv
from supabase import acreate_client, Client

# Load environment variables
load_dotenv()

_supabase_client: Client | None = None

async def get_client() -> Client:
    """
    Returns the Supabase async client singleton.
    Initializes it on first call using SUPABASE_URL and SUPABASE_KEY from environment variables.
    """
    global _supabase_client
    if _supabase_client is None:
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")
        if not url or not key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY environment variables must be set.")
        
        _supabase_client = await acreate_client(url, key)
    
    return _supabase_client

async def close_client() -> None:
    """
    Cleanly closes the Supabase client HTTP sessions to release connections.
    """
    global _supabase_client
    if _supabase_client is not None:
        # Close postgrest client session
        if hasattr(_supabase_client, "postgrest") and hasattr(_supabase_client.postgrest, "aclient"):
            try:
                await _supabase_client.postgrest.aclient.aclose()
            except Exception:
                pass
        # Close storage client session
        if hasattr(_supabase_client, "storage") and hasattr(_supabase_client.storage, "aclient"):
            try:
                await _supabase_client.storage.aclient.aclose()
            except Exception:
                pass
        _supabase_client = None

