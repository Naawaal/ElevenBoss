# tests/test_deployment_changelog.py
"""Unit & integration tests for deployment changelog announcement (Feature 055)."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from apps.discord_bot.core.deployment_changelog import (
    ChangelogEntry,
    get_current_commit_sha,
    parse_latest_changelog_entry,
)
from apps.discord_bot.embeds.changelog_embeds import build_changelog_embed


def test_parse_latest_changelog_entry(tmp_path: Path) -> None:
    content = """# Changelog

## [1.4.0] - 2026-08-05

### Added
- Instant Ranked ghost opponents.
- Ranked AI backfill fallback.

### Fixed
- PvP recovery and snapshot integrity.

## [1.3.0] - 2026-07-20

### Added
- Previous feature.
"""
    file = tmp_path / "change_log.md"
    file.write_text(content, encoding="utf-8")

    entry = parse_latest_changelog_entry(file)
    assert entry is not None
    assert entry.version == "1.4.0"
    assert entry.date == "2026-08-05"
    assert "Added" in entry.sections
    assert len(entry.sections["Added"]) == 2
    assert "Fixed" in entry.sections
    assert len(entry.sections["Fixed"]) == 1


def test_parse_latest_changelog_missing_file(tmp_path: Path) -> None:
    file = tmp_path / "nonexistent.md"
    assert parse_latest_changelog_entry(file) is None


def test_get_current_commit_sha() -> None:
    with patch.dict("os.environ", {"GIT_COMMIT_SHA": "ea590ab1ec3ba08b7f6f9a65fc1a447ff41ccc24"}):
        sha = get_current_commit_sha()
        assert sha == "ea590ab1ec3ba08b7f6f9a65fc1a447ff41ccc24"


def test_build_changelog_embed() -> None:
    entry = ChangelogEntry(
        version="1.4.0",
        date="2026-08-05",
        sections={
            "Added": ["Instant Ranked ghost opponents", "Ranked AI backfill"],
            "Fixed": ["PvP recovery integrity"],
        },
        raw_heading="## [1.4.0] - 2026-08-05",
    )
    embed = build_changelog_embed(entry, "ea590ab12345")
    assert "1.4.0" in (embed.title or "")
    assert len(embed.fields) == 2
    assert "ea590ab" in (embed.footer.text or "")
