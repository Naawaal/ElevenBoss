# apps/discord_bot/core/help_commands.py
"""Harvest and format the live slash command tree for /help Commands Reference."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

RESTRICTED_NOTE = "*(Admin/owner only)*"
EMPTY_DESCRIPTION = "(no description)"
EMPTY_COMMANDS_COPY = (
    "Commands unavailable — try again after the bot finishes syncing."
)


@dataclass(frozen=True)
class CommandEntry:
    qualified_name: str
    description: str
    restricted: bool


def _check_names(check: Any) -> str:
    parts = [
        getattr(check, "__name__", "") or "",
        getattr(check, "__qualname__", "") or "",
        getattr(getattr(check, "__wrapped__", None), "__name__", "") or "",
        getattr(getattr(check, "__func__", None), "__name__", "") or "",
    ]
    return " ".join(parts).lower()


def _is_restricted(cmd: Any) -> bool:
    """True only for owner/admin gates — not player gates like ensure_registered."""
    perms = getattr(cmd, "default_permissions", None)
    if perms is not None:
        return True
    for check in getattr(cmd, "checks", None) or ():
        blob = _check_names(check)
        if "is_owner" in blob or "admin_only" in blob or blob.endswith(".owner"):
            return True
    return False


def harvest_command_entries(tree: Any) -> list[CommandEntry]:
    """Walk an app command tree; return leaf commands only."""
    entries: list[CommandEntry] = []
    if tree is None:
        return entries

    walk = getattr(tree, "walk_commands", None)
    if walk is None:
        return entries

    try:
        from discord import app_commands
    except ImportError:  # pragma: no cover
        app_commands = None  # type: ignore[assignment]

    for cmd in walk():
        if app_commands is not None and isinstance(cmd, app_commands.Group):
            continue
        # Groups without discord import: skip objects that expose .commands children only
        if getattr(cmd, "commands", None) is not None and not hasattr(cmd, "callback"):
            continue
        name = getattr(cmd, "qualified_name", None) or getattr(cmd, "name", None)
        if not name:
            continue
        desc = getattr(cmd, "description", None) or ""
        entries.append(
            CommandEntry(
                qualified_name=str(name),
                description=str(desc),
                restricted=_is_restricted(cmd),
            )
        )

    entries.sort(key=lambda e: e.qualified_name.lower())
    return entries


def format_command_lines(entries: list[CommandEntry]) -> list[str]:
    """Human-readable command lines for embeds."""
    if not entries:
        return [EMPTY_COMMANDS_COPY]
    lines: list[str] = []
    for entry in entries:
        desc = (entry.description or "").strip() or EMPTY_DESCRIPTION
        suffix = f" {RESTRICTED_NOTE}" if entry.restricted else ""
        lines.append(f"`/{entry.qualified_name}` — {desc}{suffix}")
    return lines


def chunk_text_blocks(lines: list[str], *, max_chars: int = 1000) -> list[str]:
    """Chunk lines into blocks that fit Discord embed field values."""
    if not lines:
        return [EMPTY_COMMANDS_COPY]
    blocks: list[str] = []
    current = ""
    for line in lines:
        piece = line if not current else f"{current}\n{line}"
        if len(piece) <= max_chars:
            current = piece
            continue
        if current:
            blocks.append(current)
        if len(line) <= max_chars:
            current = line
        else:
            # Hard-split oversized single lines
            start = 0
            while start < len(line):
                blocks.append(line[start : start + max_chars])
                start += max_chars
            current = ""
    if current:
        blocks.append(current)
    return blocks or [EMPTY_COMMANDS_COPY]
