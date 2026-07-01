# tests/test_match_engine.py

import unittest
from app.engine.match_engine import (
    MatchPlayerInput,
    MatchTeamInput,
    MatchSimulationInput,
    simulate_match,
)
from app.engine.team_strength import calculate_team_strength


def create_player(player_id: str, slot: str, position: str, overall: int, fitness: int = 100) -> MatchPlayerInput:
    return MatchPlayerInput(
        player_id=player_id,
        name=f"Player {player_id}",
        position=position,
        slot=slot,
        overall=overall,
        potential=overall + 5,
        fitness=fitness,
        morale=80,
    )


def create_standard_xi(prefix: str, overall: int, fitness: int = 100) -> list[MatchPlayerInput]:
    return [
        create_player(f"{prefix}_gk", "GK", "GK", overall, fitness),
        create_player(f"{prefix}_lb", "LB", "LB", overall, fitness),
        create_player(f"{prefix}_cb1", "CB1", "CB", overall, fitness),
        create_player(f"{prefix}_cb2", "CB2", "CB", overall, fitness),
        create_player(f"{prefix}_rb", "RB", "RB", overall, fitness),
        create_player(f"{prefix}_lm", "LM", "LM", overall, fitness),
        create_player(f"{prefix}_cm1", "CM1", "CM", overall, fitness),
        create_player(f"{prefix}_cm2", "CM2", "CM", overall, fitness),
        create_player(f"{prefix}_rm", "RM", "RM", overall, fitness),
        create_player(f"{prefix}_st1", "ST1", "ST", overall, fitness),
        create_player(f"{prefix}_st2", "ST2", "ST", overall, fitness),
    ]


class TestMatchEngine(unittest.TestCase):

    def setUp(self):
        self.home_players = create_standard_xi("h", 80)
        self.away_players = create_standard_xi("a", 70)
        
        self.home_team = MatchTeamInput(
            club_id="club_home",
            club_name="Home FC",
            formation="4-4-2",
            players=self.home_players,
            is_home=True
        )
        self.away_team = MatchTeamInput(
            club_id="club_away",
            club_name="Away FC",
            formation="4-4-2",
            players=self.away_players,
            is_home=False
        )

    def test_same_seed_produces_same_result(self):
        """Simulation must be 100% deterministic for a given seed."""
        sim_input = MatchSimulationInput(
            fixture_id="fixture_1",
            week=1,
            home_team=self.home_team,
            away_team=self.away_team,
            seed=42
        )
        res1 = simulate_match(sim_input)
        res2 = simulate_match(sim_input)
        
        self.assertEqual(res1.home_goals, res2.home_goals)
        self.assertEqual(res1.away_goals, res2.away_goals)
        self.assertEqual(res1.home_possession, res2.home_possession)
        self.assertEqual(res1.home_shots, res2.home_shots)
        self.assertEqual(res1.home_shots_on_target, res2.home_shots_on_target)
        self.assertEqual(len(res1.goals), len(res2.goals))
        self.assertEqual(res1.motm_player_id, res2.motm_player_id)
        self.assertEqual(res1.player_ratings, res2.player_ratings)

    def test_different_seed_can_produce_different_result(self):
        """Different seeds produce varied results."""
        results = []
        for i in range(10):
            sim_input = MatchSimulationInput(
                fixture_id="fixture_1",
                week=1,
                home_team=self.home_team,
                away_team=self.away_team,
                seed=1000 + i
            )
            res = simulate_match(sim_input)
            results.append((res.home_goals, res.away_goals))
            
        # Assert that not all results are identical
        self.assertGreater(len(set(results)), 1)

    def test_stronger_team_generally_has_advantage(self):
        """A team with 90 overall vs 50 overall should win a clear majority of simulations."""
        strong_players = create_standard_xi("h", 90)
        weak_players = create_standard_xi("a", 50)
        
        home_strong = MatchTeamInput(
            club_id="club_home",
            club_name="Strong FC",
            formation="4-4-2",
            players=strong_players,
            is_home=True
        )
        away_weak = MatchTeamInput(
            club_id="club_away",
            club_name="Weak FC",
            formation="4-4-2",
            players=weak_players,
            is_home=False
        )
        
        strong_wins = 0
        total_runs = 50
        for i in range(total_runs):
            sim_input = MatchSimulationInput(
                fixture_id="fixture_1",
                week=1,
                home_team=home_strong,
                away_team=away_weak,
                seed=5000 + i
            )
            res = simulate_match(sim_input)
            if res.home_goals > res.away_goals:
                strong_wins += 1
                
        # Strong home team should win at least 75% of the matches
        win_rate = strong_wins / total_runs
        self.assertGreaterEqual(win_rate, 0.75)

    def test_statistics_validity(self):
        """Simulation stats must be logical and within bounds."""
        sim_input = MatchSimulationInput(
            fixture_id="fixture_1",
            week=1,
            home_team=self.home_team,
            away_team=self.away_team,
            seed=77
        )
        res = simulate_match(sim_input)
        
        self.assertGreaterEqual(res.home_goals, 0)
        self.assertGreaterEqual(res.away_goals, 0)
        self.assertEqual(res.home_possession + res.away_possession, 100)
        self.assertGreaterEqual(res.home_possession, 35)
        self.assertLessEqual(res.home_possession, 65)
        self.assertGreaterEqual(res.home_shots, res.home_shots_on_target)
        self.assertGreaterEqual(res.away_shots, res.away_shots_on_target)
        self.assertGreaterEqual(res.home_shots_on_target, res.home_goals)
        self.assertGreaterEqual(res.away_shots_on_target, res.away_goals)

    def test_event_attribution(self):
        """Goalscorers, assists, and MOTM must belong to starting lineups."""
        sim_input = MatchSimulationInput(
            fixture_id="fixture_1",
            week=1,
            home_team=self.home_team,
            away_team=self.away_team,
            seed=22
        )
        res = simulate_match(sim_input)
        
        home_ids = {p.player_id for p in self.home_players}
        away_ids = {p.player_id for p in self.away_players}
        all_ids = home_ids | away_ids
        
        # Verify goals
        for goal in res.goals:
            if goal.club_id == "club_home":
                self.assertIn(goal.scorer_id, home_ids)
                if goal.assist_id:
                    self.assertIn(goal.assist_id, home_ids)
                    self.assertNotEqual(goal.scorer_id, goal.assist_id)
            else:
                self.assertIn(goal.scorer_id, away_ids)
                if goal.assist_id:
                    self.assertIn(goal.assist_id, away_ids)
                    self.assertNotEqual(goal.scorer_id, goal.assist_id)
                    
        # Verify MOTM
        if res.motm_player_id:
            self.assertIn(res.motm_player_id, all_ids)

    def test_team_strength_calculations(self):
        """Verify GK, DEF, MID, ATT strengths respond to overall & positioning."""
        # 1. Standard 80 overall team
        strength = calculate_team_strength("4-4-2", self.home_players, is_home=False)
        self.assertGreater(strength.defense, 70)
        self.assertGreater(strength.midfield, 70)
        self.assertGreater(strength.attack, 70)
        self.assertGreater(strength.goalkeeper, 70)
        
        # 2. Out-of-position penalty
        # Swap GK with ST in GK slot
        bad_players = self.home_players.copy()
        # Find GK player and ST player
        gk_idx = next(i for i, p in enumerate(bad_players) if p.slot == "GK")
        st_idx = next(i for i, p in enumerate(bad_players) if p.slot == "ST1")
        
        # Swap slots
        p_gk = bad_players[gk_idx]
        p_st = bad_players[st_idx]
        
        bad_players[gk_idx] = MatchPlayerInput(p_gk.player_id, p_gk.name, p_gk.position, "ST1", p_gk.overall, p_gk.potential, p_gk.fitness)
        bad_players[st_idx] = MatchPlayerInput(p_st.player_id, p_st.name, p_st.position, "GK", p_st.overall, p_st.potential, p_st.fitness)
        
        bad_strength = calculate_team_strength("4-4-2", bad_players, is_home=False)
        # GK strength should drop heavily due to outfield player in goal
        self.assertLess(bad_strength.goalkeeper, 30)

    def test_missing_morale_does_not_crash(self):
        """Simulation should not crash if optional morale field is None."""
        players_no_morale = [
            MatchPlayerInput(
                player_id=p.player_id,
                name=p.name,
                position=p.position,
                slot=p.slot,
                overall=p.overall,
                potential=p.potential,
                fitness=p.fitness,
                morale=None,
            )
            for p in self.home_players
        ]
        home_team_no_morale = MatchTeamInput(
            club_id="club_home",
            club_name="Home FC",
            formation="4-4-2",
            players=players_no_morale,
            is_home=True
        )
        sim_input = MatchSimulationInput(
            fixture_id="fixture_1",
            week=1,
            home_team=home_team_no_morale,
            away_team=self.away_team,
            seed=123
        )
        # Should simulate successfully
        res = simulate_match(sim_input)
        self.assertIsNotNone(res)
        self.assertEqual(res.home_possession + res.away_possession, 100)
