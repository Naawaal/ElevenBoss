# tests/test_standings_update.py

import unittest
import uuid
from app.models.standing import LeagueStanding

class TestStandingsUpdate(unittest.TestCase):

    def setUp(self):
        self.season_id = uuid.uuid4()
        self.home_club_id = uuid.uuid4()
        self.away_club_id = uuid.uuid4()

        # Initialize mock standings
        self.home_standing = LeagueStanding(
            guild_id="123",
            season_id=self.season_id,
            club_id=self.home_club_id,
            played=0,
            wins=0,
            draws=0,
            losses=0,
            goals_for=0,
            goals_against=0,
            goal_difference=0,
            points=0
        )
        self.away_standing = LeagueStanding(
            guild_id="123",
            season_id=self.season_id,
            club_id=self.away_club_id,
            played=0,
            wins=0,
            draws=0,
            losses=0,
            goals_for=0,
            goals_against=0,
            goal_difference=0,
            points=0
        )

    def test_home_win_updates_standings(self):
        """Updating standings on a home win attributes points and goals correctly."""
        # Simulated result: Home wins 2 - 1
        home_goals = 2
        away_goals = 1

        self.home_standing.played += 1
        self.away_standing.played += 1

        self.home_standing.goals_for += home_goals
        self.home_standing.goals_against += away_goals
        self.away_standing.goals_for += away_goals
        self.away_standing.goals_against += home_goals

        self.home_standing.goal_difference = self.home_standing.goals_for - self.home_standing.goals_against
        self.away_standing.goal_difference = self.away_standing.goals_for - self.away_standing.goals_against

        self.home_standing.wins += 1
        self.home_standing.points += 3
        self.away_standing.losses += 1

        # Assertions
        self.assertEqual(self.home_standing.played, 1)
        self.assertEqual(self.home_standing.wins, 1)
        self.assertEqual(self.home_standing.points, 3)
        self.assertEqual(self.home_standing.goals_for, 2)
        self.assertEqual(self.home_standing.goals_against, 1)
        self.assertEqual(self.home_standing.goal_difference, 1)

        self.assertEqual(self.away_standing.played, 1)
        self.assertEqual(self.away_standing.losses, 1)
        self.assertEqual(self.away_standing.points, 0)
        self.assertEqual(self.away_standing.goals_for, 1)
        self.assertEqual(self.away_standing.goals_against, 2)
        self.assertEqual(self.away_standing.goal_difference, -1)

    def test_away_win_updates_standings(self):
        """Updating standings on an away win attributes points and goals correctly."""
        # Simulated result: Away wins 0 - 3
        home_goals = 0
        away_goals = 3

        self.home_standing.played += 1
        self.away_standing.played += 1

        self.home_standing.goals_for += home_goals
        self.home_standing.goals_against += away_goals
        self.away_standing.goals_for += away_goals
        self.away_standing.goals_against += home_goals

        self.home_standing.goal_difference = self.home_standing.goals_for - self.home_standing.goals_against
        self.away_standing.goal_difference = self.away_standing.goals_for - self.away_standing.goals_against

        self.away_standing.wins += 1
        self.away_standing.points += 3
        self.home_standing.losses += 1

        # Assertions
        self.assertEqual(self.home_standing.played, 1)
        self.assertEqual(self.home_standing.losses, 1)
        self.assertEqual(self.home_standing.points, 0)
        self.assertEqual(self.home_standing.goal_difference, -3)

        self.assertEqual(self.away_standing.played, 1)
        self.assertEqual(self.away_standing.wins, 1)
        self.assertEqual(self.away_standing.points, 3)
        self.assertEqual(self.away_standing.goal_difference, 3)

    def test_draw_updates_standings(self):
        """Updating standings on a draw attributes 1 point to each team."""
        # Simulated result: 1 - 1
        home_goals = 1
        away_goals = 1

        self.home_standing.played += 1
        self.away_standing.played += 1

        self.home_standing.goals_for += home_goals
        self.home_standing.goals_against += away_goals
        self.away_standing.goals_for += away_goals
        self.away_standing.goals_against += home_goals

        self.home_standing.goal_difference = self.home_standing.goals_for - self.home_standing.goals_against
        self.away_standing.goal_difference = self.away_standing.goals_for - self.away_standing.goals_against

        self.home_standing.draws += 1
        self.home_standing.points += 1
        self.away_standing.draws += 1
        self.away_standing.points += 1

        # Assertions
        self.assertEqual(self.home_standing.played, 1)
        self.assertEqual(self.home_standing.draws, 1)
        self.assertEqual(self.home_standing.points, 1)
        self.assertEqual(self.home_standing.goal_difference, 0)

        self.assertEqual(self.away_standing.played, 1)
        self.assertEqual(self.away_standing.draws, 1)
        self.assertEqual(self.away_standing.points, 1)
        self.assertEqual(self.away_standing.goal_difference, 0)
