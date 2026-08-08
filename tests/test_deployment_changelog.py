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


def test_parse_body_edit_same_version(tmp_path: Path) -> None:
    """Body edits under the same header still yield the same version identity."""
    file = tmp_path / "change_log.md"
    file.write_text(
        "## [2.2.0] - 2026-08-08\n\n### Fixed\n- First fix.\n",
        encoding="utf-8",
    )
    first = parse_latest_changelog_entry(file)
    assert first is not None and first.version == "2.2.0"
    file.write_text(
        "## [2.2.0] - 2026-08-08\n\n### Fixed\n- First fix.\n- Second fix under same version.\n",
        encoding="utf-8",
    )
    second = parse_latest_changelog_entry(file)
    assert second is not None and second.version == first.version


@pytest.mark.asyncio
async def test_check_and_post_uses_version_only_key() -> None:
    """Claim key must be version only — different commits must not create a new key."""
    from apps.discord_bot.core.deployment_changelog import check_and_post_deployment_changelog

    entry = ChangelogEntry(
        version="2.2.0",
        date="2026-08-08",
        sections={"Changed": ["Shelved PvP"]},
        raw_heading="## [2.2.0] - 2026-08-08",
    )
    mock_bot = MagicMock()
    mock_db = MagicMock()
    mock_rpc = MagicMock()
    mock_exec = AsyncMock(return_value=MagicMock(data={"status": "already_posted"}))
    mock_db.rpc.return_value = mock_rpc
    mock_rpc.execute = mock_exec

    with (
        patch(
            "apps.discord_bot.core.deployment_changelog.parse_latest_changelog_entry",
            return_value=entry,
        ),
        patch(
            "apps.discord_bot.core.deployment_changelog.get_current_commit_sha",
            return_value="abcdef1234567890",
        ),
        patch(
            "apps.discord_bot.core.deployment_changelog.get_client",
            AsyncMock(return_value=mock_db),
        ),
        patch.dict("os.environ", {"CHANGELOG_POST_ENABLED": "true"}),
    ):
        await check_and_post_deployment_changelog(mock_bot)

    assert mock_db.rpc.called
    args = mock_db.rpc.call_args
    assert args[0][0] == "claim_deployment_changelog"
    assert args[0][1]["p_deployment_key"] == "2.2.0"
    assert ":" not in args[0][1]["p_deployment_key"]


@pytest.mark.asyncio
async def test_check_and_post_completes_only_after_send() -> None:
    from apps.discord_bot.core.deployment_changelog import check_and_post_deployment_changelog

    entry = ChangelogEntry(
        version="9.9.9",
        date="2026-08-08",
        sections={"Added": ["Test"]},
        raw_heading="## [9.9.9] - 2026-08-08",
    )
    mock_channel = AsyncMock()
    mock_channel.id = 42
    mock_channel.name = "announcements"
    mock_channel.send = AsyncMock(return_value=MagicMock(id=1))

    mock_bot = MagicMock()
    mock_db = MagicMock()
    claim_exec = AsyncMock(return_value=MagicMock(data={"status": "claimed"}))
    complete_exec = AsyncMock(return_value=MagicMock(data={"status": "completed"}))

    def rpc_side_effect(name: str, *_a, **_k):
        m = MagicMock()
        m.execute = claim_exec if name == "claim_deployment_changelog" else complete_exec
        return m

    mock_db.rpc.side_effect = rpc_side_effect

    with (
        patch(
            "apps.discord_bot.core.deployment_changelog.parse_latest_changelog_entry",
            return_value=entry,
        ),
        patch(
            "apps.discord_bot.core.deployment_changelog.get_current_commit_sha",
            return_value="deadbeef",
        ),
        patch(
            "apps.discord_bot.core.deployment_changelog.get_client",
            AsyncMock(return_value=mock_db),
        ),
        patch(
            "apps.discord_bot.core.deployment_changelog.resolve_changelog_target_channel",
            AsyncMock(return_value=mock_channel),
        ),
        patch.dict("os.environ", {"CHANGELOG_POST_ENABLED": "true"}),
    ):
        await check_and_post_deployment_changelog(mock_bot)

    assert mock_channel.send.called
    assert complete_exec.called
    # Failed-send path: if send raises, complete must not run
    mock_channel.send = AsyncMock(side_effect=RuntimeError("discord down"))
    complete_exec.reset_mock()
    claim_exec.reset_mock()
    claim_exec.return_value = MagicMock(data={"status": "claimed"})
    with (
        patch(
            "apps.discord_bot.core.deployment_changelog.parse_latest_changelog_entry",
            return_value=entry,
        ),
        patch(
            "apps.discord_bot.core.deployment_changelog.get_current_commit_sha",
            return_value="deadbeef",
        ),
        patch(
            "apps.discord_bot.core.deployment_changelog.get_client",
            AsyncMock(return_value=mock_db),
        ),
        patch(
            "apps.discord_bot.core.deployment_changelog.resolve_changelog_target_channel",
            AsyncMock(return_value=mock_channel),
        ),
        patch.dict("os.environ", {"CHANGELOG_POST_ENABLED": "true"}),
    ):
        await check_and_post_deployment_changelog(mock_bot)
    assert not complete_exec.called
