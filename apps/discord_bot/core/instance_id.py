# apps/discord_bot/core/instance_id.py
"""Stable process identity for logs/metrics (050 / US-43 multi-instance prep)."""
from __future__ import annotations

import os
import socket


def get_instance_id() -> str:
    explicit = (os.environ.get("INSTANCE_ID") or "").strip()
    if explicit:
        return explicit
    host = socket.gethostname() or "host"
    return f"{host}:{os.getpid()}"
