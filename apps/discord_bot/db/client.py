# apps/discord_bot/db/client.py
from __future__ import annotations

import os

import httpx
from dotenv import load_dotenv
from supabase import AsyncClientOptions, acreate_client
from supabase._async.client import AsyncClient

# Load environment variables
load_dotenv()

_supabase_client: AsyncClient | None = None
_http_client: httpx.AsyncClient | None = None


async def get_client() -> AsyncClient:
    """
    Returns the Supabase async client singleton.
    Initializes it on first call using SUPABASE_URL and SUPABASE_KEY from environment variables.
    """
    global _supabase_client, _http_client
    if _supabase_client is None:
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")
        if not url or not key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY environment variables must be set.")

        # ponytail: Supabase HTTP/2 multiplex often raises
        # `RemoteProtocolError: ConnectionTerminated` under asyncio.gather / startup
        # recovery storms. HTTP/1.1 + transport retries is the stable path until
        # httpcore auto-retries ConnectionTerminated (encode/httpcore#683).
        # Defaults 20/5 — do not raise before 050 Phase 2 round-trip cuts (load-test first).
        max_conn = int(os.environ.get("SUPABASE_HTTP_MAX_CONNECTIONS", "20"))
        keepalive = int(os.environ.get("SUPABASE_HTTP_KEEPALIVE_CONNECTIONS", "5"))
        timeout_s = float(os.environ.get("SUPABASE_HTTP_TIMEOUT_SECONDS", "60"))
        _http_client = httpx.AsyncClient(
            http2=False,
            timeout=timeout_s,
            transport=httpx.AsyncHTTPTransport(retries=3),
            limits=httpx.Limits(
                max_connections=max_conn,
                max_keepalive_connections=keepalive,
            ),
        )
        _supabase_client = await acreate_client(
            url,
            key,
            options=AsyncClientOptions(httpx_client=_http_client),
        )

    return _supabase_client


async def close_client() -> None:
    """
    Cleanly closes the Supabase client HTTP sessions to release connections.
    """
    global _supabase_client, _http_client
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

    if _http_client is not None:
        try:
            await _http_client.aclose()
        except Exception:
            pass
        _http_client = None
