# apps/discord_bot/core/deployment_changelog.py
"""Deployment changelog parser and startup announcement service (Feature 055)."""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import discord
from discord.ext import commands

from apps.discord_bot.db.client import get_client
from apps.discord_bot.embeds.changelog_embeds import build_changelog_embed

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChangelogEntry:
    version: str
    date: str | None
    sections: dict[str, list[str]]
    raw_heading: str


VERSION_HEADING_RE = re.compile(
    r"^##\s+\[(?P<version>[^\]]+)\](?:\s+-\s+(?P<date>\d{4}-\d{2}-\d{2}))?",
    re.MULTILINE,
)
SECTION_HEADING_RE = re.compile(r"^###\s+(?P<section>Added|Changed|Fixed|Removed)", re.MULTILINE)


def parse_latest_changelog_entry(changelog_path: Path) -> ChangelogEntry | None:
    """Parse the first versioned release section from change_log.md."""
    if not changelog_path.exists():
        logger.warning("Deployment changelog skipped: %s not found", changelog_path.name)
        return None

    try:
        text = changelog_path.read_text(encoding="utf-8")
    except Exception:
        logger.exception("Failed to read %s", changelog_path)
        return None

    match = VERSION_HEADING_RE.search(text)
    if not match:
        logger.warning("Deployment changelog skipped: no valid '## [X.Y.Z]' heading in %s", changelog_path.name)
        return None

    version = match.group("version").strip()
    date_str = match.group("date").strip() if match.group("date") else None
    start_pos = match.end()

    # Find next '## ' heading to bound this version section
    next_ver = VERSION_HEADING_RE.search(text, start_pos)
    section_text = text[start_pos : next_ver.start()] if next_ver else text[start_pos:]

    sections: dict[str, list[str]] = {"Added": [], "Changed": [], "Fixed": [], "Removed": []}
    current_sec: str | None = None

    for line in section_text.splitlines():
        line_str = line.strip()
        if line_str.startswith("### "):
            sec_match = SECTION_HEADING_RE.match(line_str)
            current_sec = sec_match.group("section") if sec_match else None
        elif current_sec and line_str.startswith("- ") and len(line_str) > 2:
            item_text = line_str[2:].strip()
            if item_text:
                sections[current_sec].append(item_text)

    # Filter out empty sections
    sections = {k: v for k, v in sections.items() if v}
    if not sections:
        logger.warning("Deployment changelog skipped: version %s has no items", version)
        return None

    return ChangelogEntry(
        version=version,
        date=date_str,
        sections=sections,
        raw_heading=match.group(0),
    )


def get_current_commit_sha() -> str:
    """Read short or full commit SHA from platform environment variables."""
    for var_name in ("GIT_COMMIT_SHA", "RENDER_GIT_COMMIT", "RAILWAY_GIT_COMMIT_SHA", "HEROKU_SLUG_COMMIT"):
        val = os.environ.get(var_name, "").strip()
        if val:
            return val
    return "unknown"


async def resolve_changelog_target_channel(bot: commands.Bot) -> discord.TextChannel | None:
    """Resolve the target text channel for changelog announcements."""
    db = await get_client()

    # Priority 1: User-configured League Announce Channel from guild_config (admin /league setup)
    for guild in sorted(bot.guilds, key=lambda g: g.id):
        me = guild.me
        if me is None:
            continue
        try:
            res = await db.table("guild_config").select("league_channel_id").eq("guild_id", guild.id).maybe_single().execute()
            if res and res.data and res.data.get("league_channel_id"):
                cid = int(res.data["league_channel_id"])
                ch = guild.get_channel(cid)
                if isinstance(ch, discord.TextChannel) and ch.permissions_for(me).send_messages:
                    return ch
        except Exception:
            logger.debug("Failed to resolve guild_config league_channel_id for guild %s", guild.id, exc_info=True)

    # Priority 2: CHANGELOG_CHANNEL_ID environment variable
    raw_env_cid = os.environ.get("CHANGELOG_CHANNEL_ID", "").strip()
    if raw_env_cid.isdigit():
        env_cid = int(raw_env_cid)
        ch = bot.get_channel(env_cid)
        if isinstance(ch, discord.TextChannel) and ch.permissions_for(ch.guild.me).send_messages:
            return ch

    # Priority 3: First writable non-thread text channel across bot guilds
    for guild in sorted(bot.guilds, key=lambda g: g.id):
        me = guild.me
        if me is None:
            continue
        for ch in sorted(guild.text_channels, key=lambda c: c.position):
            perms = ch.permissions_for(me)
            if perms.send_messages and perms.embed_links:
                return ch

    return None


async def check_and_post_deployment_changelog(bot: commands.Bot) -> None:
    """Check whether current deployment changelog should be posted and post it once."""
    enabled_env = os.environ.get("CHANGELOG_POST_ENABLED", "true").strip().lower()
    if enabled_env not in ("true", "1", "yes"):
        logger.info("Deployment changelog skipped — disabled via CHANGELOG_POST_ENABLED env")
        return

    root_dir = Path(".").resolve()
    changelog_path = root_dir / "change_log.md"
    entry = parse_latest_changelog_entry(changelog_path)
    if entry is None:
        return

    commit = get_current_commit_sha()
    deployment_key = f"{entry.version}:{commit[:7]}"

    db = await get_client()

    # Claim deployment atomically
    try:
        res = await db.rpc("claim_deployment_changelog", {
            "p_deployment_key": deployment_key,
            "p_instance_id": str(os.getpid()),
        }).execute()
        claim_data = res.data if isinstance(res.data, dict) else {}
        status = claim_data.get("status")
        if status != "claimed":
            logger.info("Deployment changelog skipped — status: %s for key %s", status, deployment_key)
            return
    except Exception:
        logger.exception("Failed to claim deployment changelog for key %s", deployment_key)
        return

    # Resolve channel
    channel = await resolve_changelog_target_channel(bot)
    if channel is None:
        logger.warning("Deployment changelog skipped: no writable target channel found")
        return

    # Post changelog embed
    try:
        embed = build_changelog_embed(entry, commit)
        msg = await channel.send(embed=embed)
        logger.info("Posted deployment changelog to #%s (id: %s) for key %s", channel.name, msg.id, deployment_key)

        # Complete claim in database
        await db.rpc("complete_deployment_changelog", {
            "p_deployment_key": deployment_key,
            "p_version": entry.version,
            "p_commit": commit[:7],
            "p_channel_id": channel.id,
        }).execute()
    except Exception:
        logger.exception("Failed to post deployment changelog to channel %s", channel.id)
