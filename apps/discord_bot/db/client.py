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
