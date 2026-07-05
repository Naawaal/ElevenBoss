"""
Fixture Generator Engine — Pure fixture generation logic.

No Discord imports. No database imports.
All functions are deterministic and side-effect free.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class GeneratedFixture:
    """
    A single generated fixture pairing.
    Immutable by design — the engine only produces values, never mutates state.
    """
    week: int
    home_club_id: str
    away_club_id: str


def generate_round_robin_fixtures(
    club_ids: list[str],
    double_round_robin: bool = False,
) -> list[GeneratedFixture]:
    """
    Generate a round-robin fixture schedule using the classic circle/polygon
    rotation algorithm.

    Rules guaranteed:
    - Every club plays exactly once per week.
    - No club plays itself.
    - No duplicate pairings (single round-robin).
    - Every pair of clubs plays exactly once (single) or twice (double).
    - Double round-robin reverses home/away in the second half.
    - Weeks are numbered starting from 1.
    - Generation is deterministic for the same club order.

    Args:
        club_ids: Ordered list of unique club ID strings.
        double_round_robin: If True, generate home+away legs (double round-robin).

    Returns:
        Ordered list of GeneratedFixture objects.

    Raises:
        ValueError: If fewer than 2 clubs are provided.
        ValueError: If an odd number of clubs is provided (V1 only supports even counts).
    """
    n = len(club_ids)

    if n < 2:
        raise ValueError(f"At least 2 clubs are required to generate fixtures. Got {n}.")

    if n % 2 != 0:
        raise ValueError(
            f"An odd number of clubs ({n}) is not supported. "
            "V1 league sizes are 8, 10, 12, or 16 (all even). "
            "The service layer should prevent this."
        )

    fixtures: list[GeneratedFixture] = []
    weeks_in_half = n - 1  # Single round-robin has (n-1) weeks

    # --- Circle / Polygon Rotation Algorithm ---
    #
    # Fix the first club in position 0, rotate the remaining (n-1) clubs
    # around it. Each rotation produces one week's worth of fixtures.
    #
    # For week k (0-indexed), the rotation places clubs as:
    #   positions[0] = club_ids[0]   (fixed)
    #   positions[i] = club_ids[((i - 1 + k) % (n - 1)) + 1]  for i in 1..n-1
    #
    # Then pair position 0 with position n-1,
    #      position 1 with position n-2, etc.
    # Alternate home/away by week parity to balance scheduling.

    for week_index in range(weeks_in_half):
        week_num = week_index + 1  # 1-indexed

        # Build the rotated ring for this week
        ring = [club_ids[0]]
        for i in range(1, n):
            ring.append(club_ids[((i - 1 + week_index) % (n - 1)) + 1])

        # Pair clubs: (ring[i], ring[n-1-i]) for i in 0..n//2-1
        for i in range(n // 2):
            a = ring[i]
            b = ring[n - 1 - i]
            # Alternate home/away: even week_index → a is home, odd → b is home
            if week_index % 2 == 0:
                fixtures.append(GeneratedFixture(week=week_num, home_club_id=a, away_club_id=b))
            else:
                fixtures.append(GeneratedFixture(week=week_num, home_club_id=b, away_club_id=a))

    if double_round_robin:
        # Second half: same matchups but home/away reversed, weeks offset by n-1
        second_half: list[GeneratedFixture] = []
        for f in fixtures:
            second_half.append(GeneratedFixture(
                week=f.week + weeks_in_half,
                home_club_id=f.away_club_id,
                away_club_id=f.home_club_id,
            ))
        fixtures.extend(second_half)

    return fixtures


def expected_fixture_counts(club_count: int, double_round_robin: bool = False) -> dict:
    """
    Returns the expected fixture metrics for a given club count.
    Useful for validation and display.

    Args:
        club_count: Number of clubs (must be even and >= 2).
        double_round_robin: Whether double round-robin is used.

    Returns:
        Dict with keys: total_weeks, fixtures_per_week, total_fixtures.
    """
    if club_count < 2 or club_count % 2 != 0:
        raise ValueError(f"club_count must be an even number >= 2, got {club_count}.")

    weeks = club_count - 1
    per_week = club_count // 2
    total = club_count * (club_count - 1) // 2

    if double_round_robin:
        weeks *= 2
        total *= 2

    return {
        "total_weeks": weeks,
        "fixtures_per_week": per_week,
        "total_fixtures": total,
    }
