"""Unit tests for /help catalog, docs URLs, and command-list formatting."""
from __future__ import annotations

from types import SimpleNamespace

from apps.discord_bot.core.help_catalog import (
    DOCS_BASE,
    REQUIRED_TOPIC_IDS,
    get_topic,
    list_topics,
    resolve_docs_url,
)
from apps.discord_bot.core.help_commands import (
    EMPTY_COMMANDS_COPY,
    EMPTY_DESCRIPTION,
    RESTRICTED_NOTE,
    CommandEntry,
    chunk_text_blocks,
    format_command_lines,
    harvest_command_entries,
)


def test_catalog_has_exact_required_ids() -> None:
    ids = {t.id for t in list_topics()}
    assert ids == set(REQUIRED_TOPIC_IDS)
    assert len(ids) == len(list_topics())


def test_resolve_docs_url_fallback_and_join() -> None:
    assert resolve_docs_url(None) == DOCS_BASE
    assert resolve_docs_url("") == DOCS_BASE
    assert resolve_docs_url("   ") == DOCS_BASE
    joined = resolve_docs_url("league")
    assert joined.startswith(DOCS_BASE)
    assert "league" in joined


def test_get_topic_by_id_and_alias() -> None:
    assert get_topic("league") is not None
    assert get_topic("LEAGUE") is not None
    assert get_topic("not-real") is None


def test_format_command_lines_restricted_and_empty_desc() -> None:
    lines = format_command_lines(
        [
            CommandEntry("admin", "", True),
            CommandEntry("squad", "Squad hub", False),
        ]
    )
    assert RESTRICTED_NOTE in lines[0]
    assert EMPTY_DESCRIPTION in lines[0]
    assert "`/admin`" in lines[0]
    assert "`/squad`" in lines[1]
    assert RESTRICTED_NOTE not in lines[1]


def test_format_command_lines_empty() -> None:
    assert format_command_lines([]) == [EMPTY_COMMANDS_COPY]


def test_chunk_text_blocks() -> None:
    lines = [f"line-{i}-" + ("x" * 80) for i in range(20)]
    blocks = chunk_text_blocks(lines, max_chars=200)
    assert len(blocks) >= 2
    assert all(len(b) <= 200 for b in blocks)


def test_harvest_skips_groups_and_marks_owner_only() -> None:
    def ensure_registered(_i):  # player gate — must NOT mark Admin/owner
        return True

    def is_owner(_i):
        return True

    leaf = SimpleNamespace(
        qualified_name="help",
        description="Guide",
        checks=(),
        default_permissions=None,
        callback=lambda: None,
    )
    registered = SimpleNamespace(
        qualified_name="battle hub",
        description="Hub",
        checks=(ensure_registered,),
        default_permissions=None,
        callback=lambda: None,
    )
    restricted = SimpleNamespace(
        qualified_name="admin",
        description="Admin",
        checks=(is_owner,),
        default_permissions=None,
        callback=lambda: None,
    )
    group = SimpleNamespace(
        qualified_name="battle",
        description="Arena",
        checks=(),
        default_permissions=None,
        commands=[leaf],
    )

    class FakeTree:
        def walk_commands(self):
            yield group
            yield leaf
            yield registered
            yield restricted

    entries = harvest_command_entries(FakeTree())
    names = {e.qualified_name for e in entries}
    assert "help" in names
    assert "admin" in names
    assert "battle hub" in names
    hub = next(e for e in entries if e.qualified_name == "battle hub")
    assert hub.restricted is False
    admin = next(e for e in entries if e.qualified_name == "admin")
    assert admin.restricted is True
