"""
Tests for ClubService — name validation, normalization, and club creation.
"""
import pytest
from app.services.club_service import ClubService, ClubNameError


class TestNormalizeClubName:
    def test_basic_casefold(self):
        assert ClubService.normalize_club_name("Arsenal FC") == "arsenal fc"

    def test_collapse_internal_whitespace(self):
        assert ClubService.normalize_club_name("Red   Lions") == "red lions"

    def test_strip_leading_trailing(self):
        assert ClubService.normalize_club_name("  City  ") == "city"

    def test_unicode_casefold(self):
        # Casefold is stricter than lower()
        assert ClubService.normalize_club_name("FC NAIROBI") == "fc nairobi"

    def test_preserves_hyphens_apostrophes(self):
        result = ClubService.normalize_club_name("O'Brien's FC")
        assert "o'brien's" in result


class TestValidateClubName:
    def test_valid_name_returned_as_display_form(self):
        result = ClubService.validate_club_name("  Arsenal FC  ")
        assert result == "Arsenal FC"

    def test_valid_name_with_hyphen(self):
        assert ClubService.validate_club_name("Red-Lions") == "Red-Lions"

    def test_valid_name_with_apostrophe(self):
        assert ClubService.validate_club_name("O'Brien") == "O'Brien"

    def test_valid_name_with_period(self):
        assert ClubService.validate_club_name("F.C. United") == "F.C. United"

    def test_too_short(self):
        with pytest.raises(ClubNameError, match="between"):
            ClubService.validate_club_name("FC")

    def test_too_long(self):
        with pytest.raises(ClubNameError, match="between"):
            ClubService.validate_club_name("A" * 41)

    def test_exactly_min_length(self):
        result = ClubService.validate_club_name("ABC")
        assert result == "ABC"

    def test_exactly_max_length(self):
        result = ClubService.validate_club_name("A" * 40)
        assert len(result) == 40

    def test_rejects_at_everyone(self):
        with pytest.raises(ClubNameError, match="mention"):
            ClubService.validate_club_name("@everyone")

    def test_rejects_at_here(self):
        with pytest.raises(ClubNameError, match="mention"):
            ClubService.validate_club_name("Best @here Club")

    def test_rejects_http_url(self):
        with pytest.raises(ClubNameError, match="URL"):
            ClubService.validate_club_name("http://spam.com")

    def test_rejects_www_url(self):
        with pytest.raises(ClubNameError, match="URL"):
            ClubService.validate_club_name("FC www.spam.com")

    def test_rejects_discord_invite(self):
        with pytest.raises(ClubNameError, match="invite"):
            ClubService.validate_club_name("discord.gg/abc")

    def test_rejects_emoji_only_special_chars(self):
        # Brackets are not in the allowed set
        with pytest.raises(ClubNameError, match="invalid characters"):
            ClubService.validate_club_name("FC [Elite]")

    def test_rejects_symbol_only(self):
        with pytest.raises(ClubNameError, match="at least one letter"):
            ClubService.validate_club_name("---")

    def test_empty_string(self):
        with pytest.raises(ClubNameError, match="empty"):
            ClubService.validate_club_name("   ")


class TestNormalizeRoundTrip:
    """Verify that validate then normalize gives stable, idempotent results."""

    def test_round_trip_stable(self):
        raw = "  My Great Club FC  "
        display = ClubService.validate_club_name(raw)
        normalized = ClubService.normalize_club_name(display)
        assert display == "My Great Club FC"
        assert normalized == "my great club fc"

    def test_different_casing_produces_same_normalized(self):
        a = ClubService.normalize_club_name("Arsenal FC")
        b = ClubService.normalize_club_name("ARSENAL FC")
        assert a == b
