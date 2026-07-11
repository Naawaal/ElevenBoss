# tests/test_api_errors.py
from __future__ import annotations

from postgrest.exceptions import APIError

from apps.discord_bot.core.api_errors import api_error_message


def test_api_error_string_dict_payload() -> None:
    exc = APIError({"message": "Insufficient action energy", "code": "P0001"})
    msg = api_error_message(exc)
    assert msg == (
        "Not enough **action energy**. Regenerates +1 every 4 minutes, or buy a refill in `/store`."
    )
    assert "{" not in msg


def test_api_error_dict_payload() -> None:
    exc = APIError({"message": "Insufficient coins"})
    assert "coins" in api_error_message(exc).lower()
