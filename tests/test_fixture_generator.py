"""
Tests for the fixture generator engine.

All tests are pure — no database, no Discord connection needed.
Tests validate the round-robin algorithm's mathematical correctness.
"""

import unittest
from itertools import combinations

from app.engine.fixture_generator import (
    generate_round_robin_fixtures,
    expected_fixture_counts,
    GeneratedFixture,
)


def make_club_ids(n: int) -> list[str]:
    """Generate n simple club ID strings for testing."""
    return [f"club_{i:02d}" for i in range(1, n + 1)]


class TestFixtureGeneratorCounts(unittest.TestCase):
    """Verify correct fixture and week counts for each supported league size."""

    def _assert_counts(self, club_count: int, expected_weeks: int, expected_per_week: int, expected_total: int):
        club_ids = make_club_ids(club_count)
        fixtures = generate_round_robin_fixtures(club_ids)

        # Total fixtures
        self.assertEqual(len(fixtures), expected_total,
            f"{club_count} clubs: expected {expected_total} total fixtures, got {len(fixtures)}")

        # Total weeks
        weeks_found = {f.week for f in fixtures}
        self.assertEqual(len(weeks_found), expected_weeks,
            f"{club_count} clubs: expected {expected_weeks} unique weeks, got {len(weeks_found)}")

        # Fixtures per week
        for week in weeks_found:
            week_fixtures = [f for f in fixtures if f.week == week]
            self.assertEqual(len(week_fixtures), expected_per_week,
                f"{club_count} clubs week {week}: expected {expected_per_week} fixtures, got {len(week_fixtures)}")

    def test_8_clubs(self):
        self._assert_counts(8, expected_weeks=7, expected_per_week=4, expected_total=28)

    def test_10_clubs(self):
        self._assert_counts(10, expected_weeks=9, expected_per_week=5, expected_total=45)

    def test_12_clubs(self):
        self._assert_counts(12, expected_weeks=11, expected_per_week=6, expected_total=66)

    def test_16_clubs(self):
        self._assert_counts(16, expected_weeks=15, expected_per_week=8, expected_total=120)


class TestFixtureGeneratorRules(unittest.TestCase):
    """Verify the structural correctness rules of the round-robin algorithm."""

    def _generate(self, n: int):
        return generate_round_robin_fixtures(make_club_ids(n))

    def test_no_club_plays_itself(self):
        """No fixture should have home_club_id == away_club_id."""
        for n in (8, 10, 12, 16):
            fixtures = self._generate(n)
            for f in fixtures:
                self.assertNotEqual(f.home_club_id, f.away_club_id,
                    f"{n} clubs: club plays itself — {f}")

    def test_no_duplicate_pairings_single_round_robin(self):
        """Every unordered pair appears exactly once in a single round-robin."""
        for n in (8, 10, 12, 16):
            fixtures = self._generate(n)
            # Normalize each fixture to an unordered frozenset pair
            pairs = [frozenset([f.home_club_id, f.away_club_id]) for f in fixtures]
            # No duplicates
            self.assertEqual(len(pairs), len(set(pairs)),
                f"{n} clubs: duplicate pairings found")
            # All combinations present
            club_ids = make_club_ids(n)
            all_pairs = {frozenset(pair) for pair in combinations(club_ids, 2)}
            self.assertEqual(set(pairs), all_pairs,
                f"{n} clubs: not all pairs are present")

    def test_every_club_plays_once_per_week(self):
        """Each club appears exactly once per week (as home or away)."""
        for n in (8, 10, 12, 16):
            club_ids = set(make_club_ids(n))
            fixtures = self._generate(n)

            weeks = {f.week for f in fixtures}
            for week in weeks:
                week_fixtures = [f for f in fixtures if f.week == week]
                clubs_this_week: set[str] = set()
                for f in week_fixtures:
                    self.assertNotIn(f.home_club_id, clubs_this_week,
                        f"{n} clubs week {week}: {f.home_club_id} plays more than once")
                    self.assertNotIn(f.away_club_id, clubs_this_week,
                        f"{n} clubs week {week}: {f.away_club_id} plays more than once")
                    clubs_this_week.add(f.home_club_id)
                    clubs_this_week.add(f.away_club_id)
                self.assertEqual(clubs_this_week, club_ids,
                    f"{n} clubs week {week}: not all clubs appear")

    def test_deterministic_for_same_input(self):
        """Same club order always produces the identical fixture list."""
        club_ids = make_club_ids(8)
        first = generate_round_robin_fixtures(club_ids)
        second = generate_round_robin_fixtures(club_ids)
        self.assertEqual(first, second, "Fixture generation is not deterministic")

    def test_weeks_start_at_1(self):
        """Week numbers must start at 1, not 0."""
        fixtures = self._generate(8)
        min_week = min(f.week for f in fixtures)
        self.assertEqual(min_week, 1)

    def test_week_numbers_are_contiguous(self):
        """Week numbers should be a contiguous range from 1 to N-1."""
        for n in (8, 10, 12, 16):
            fixtures = self._generate(n)
            weeks = sorted({f.week for f in fixtures})
            self.assertEqual(weeks, list(range(1, n)), f"{n} clubs: weeks not contiguous: {weeks}")


class TestFixtureGeneratorEdgeCases(unittest.TestCase):
    """Edge case handling: too few clubs, odd club count."""

    def test_too_few_clubs_raises(self):
        """Fewer than 2 clubs should raise ValueError."""
        with self.assertRaises(ValueError):
            generate_round_robin_fixtures([])
        with self.assertRaises(ValueError):
            generate_round_robin_fixtures(["club_01"])

    def test_odd_club_count_raises(self):
        """V1 only supports even club counts; odd count should raise ValueError."""
        with self.assertRaises(ValueError):
            generate_round_robin_fixtures(make_club_ids(7))
        with self.assertRaises(ValueError):
            generate_round_robin_fixtures(make_club_ids(9))

    def test_two_clubs_minimum(self):
        """2 clubs should work — 1 week, 1 fixture."""
        fixtures = generate_round_robin_fixtures(["club_01", "club_02"])
        self.assertEqual(len(fixtures), 1)
        self.assertEqual(fixtures[0].week, 1)
        self.assertNotEqual(fixtures[0].home_club_id, fixtures[0].away_club_id)


class TestDoubleRoundRobin(unittest.TestCase):
    """Tests for the optional double round-robin mode."""

    def test_double_round_robin_double_count(self):
        """Double round-robin should have exactly 2x the fixtures of single."""
        club_ids = make_club_ids(8)
        single = generate_round_robin_fixtures(club_ids, double_round_robin=False)
        double = generate_round_robin_fixtures(club_ids, double_round_robin=True)
        self.assertEqual(len(double), len(single) * 2)

    def test_double_round_robin_reverses_home_away(self):
        """Every pairing in the second half must reverse home/away vs the first half."""
        club_ids = make_club_ids(8)
        fixtures = generate_round_robin_fixtures(club_ids, double_round_robin=True)
        n = 8
        half = n - 1  # 7 weeks per half

        first_half = [f for f in fixtures if f.week <= half]
        second_half = [f for f in fixtures if f.week > half]

        # Build a lookup: (home, away) -> week in first half
        first_half_pairs = {(f.home_club_id, f.away_club_id) for f in first_half}

        for f in second_half:
            # The corresponding reversed pair must exist in the first half
            reversed_pair = (f.away_club_id, f.home_club_id)
            self.assertIn(reversed_pair, first_half_pairs,
                f"Second half fixture {f} has no reversed counterpart in first half")

    def test_double_round_robin_every_pair_plays_twice(self):
        """Every unordered pair of clubs should appear exactly twice."""
        club_ids = make_club_ids(8)
        fixtures = generate_round_robin_fixtures(club_ids, double_round_robin=True)
        pair_counts: dict[frozenset, int] = {}
        for f in fixtures:
            pair = frozenset([f.home_club_id, f.away_club_id])
            pair_counts[pair] = pair_counts.get(pair, 0) + 1
        for pair, count in pair_counts.items():
            self.assertEqual(count, 2, f"Pair {pair} appears {count} times, expected 2")


class TestExpectedFixtureCounts(unittest.TestCase):
    """Tests for the expected_fixture_counts helper function."""

    def test_8_clubs_counts(self):
        c = expected_fixture_counts(8)
        self.assertEqual(c["total_weeks"], 7)
        self.assertEqual(c["fixtures_per_week"], 4)
        self.assertEqual(c["total_fixtures"], 28)

    def test_16_clubs_counts(self):
        c = expected_fixture_counts(16)
        self.assertEqual(c["total_weeks"], 15)
        self.assertEqual(c["fixtures_per_week"], 8)
        self.assertEqual(c["total_fixtures"], 120)

    def test_invalid_odd_count_raises(self):
        with self.assertRaises(ValueError):
            expected_fixture_counts(7)

    def test_invalid_zero_raises(self):
        with self.assertRaises(ValueError):
            expected_fixture_counts(0)


if __name__ == "__main__":
    unittest.main()
