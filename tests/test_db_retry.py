# tests/test_db_retry.py
"""US-43 db_retry bounds."""
from __future__ import annotations

import pytest

from apps.discord_bot.core.db_retry import is_transient_error, with_db_retry


class _Boom(Exception):
    pass


@pytest.mark.asyncio
async def test_retry_on_transient_then_success() -> None:
    calls = {"n": 0}

    async def op() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise TimeoutError("timed out")
        return "ok"

    assert await with_db_retry(op, max_attempts=3, base_delay_s=0.01) == "ok"
    assert calls["n"] == 3


@pytest.mark.asyncio
async def test_no_retry_when_not_idempotent() -> None:
    calls = {"n": 0}

    async def op() -> str:
        calls["n"] += 1
        raise TimeoutError("timed out")

    with pytest.raises(TimeoutError):
        await with_db_retry(op, max_attempts=3, base_delay_s=0.01, idempotent=False)
    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_no_retry_on_business_error() -> None:
    calls = {"n": 0}

    async def op() -> str:
        calls["n"] += 1
        raise _Boom("insufficient_coins")

    with pytest.raises(_Boom):
        await with_db_retry(op, max_attempts=3, base_delay_s=0.01)
    assert calls["n"] == 1


def test_is_transient_markers() -> None:
    assert is_transient_error(TimeoutError("x"))
    assert is_transient_error(RuntimeError("503 service"))
    assert not is_transient_error(ValueError("bad input"))
