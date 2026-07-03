# tests/test_training_engine.py

import unittest
from app.engine.training_engine import (
    TrainingWeekInput,
    TrainingWeekResult,
    calculate_training_week,
    calculate_match_development_xp,
    calculate_season_training_bonus,
)


class TestTrainingEngine(unittest.TestCase):

    def test_training_week_has_no_overall_delta(self):
        # Verify that TrainingWeekResult has no OVR delta field
        inp = TrainingWeekInput(
            player_id="p1",
            age=20,
            overall=70,
            potential=80,
            sharpness=50,
            morale=75,
            current_readiness_modifier=1.00,
            plan_type="balanced",
            intensity="normal",
            is_injured=False,
            training_pitch_level=1,
        )
        res = calculate_training_week(inp)
        self.assertFalse(hasattr(res, "overall_delta"))
        self.assertFalse(hasattr(res, "ovr_delta"))

    def test_training_week_has_no_fitness_delta(self):
        # Verify that TrainingWeekResult has no fitness delta field (since training shouldn't touch fitness)
        inp = TrainingWeekInput(
            player_id="p1",
            age=20,
            overall=70,
            potential=80,
            sharpness=50,
            morale=75,
            current_readiness_modifier=1.00,
            plan_type="balanced",
            intensity="normal",
            is_injured=False,
            training_pitch_level=1,
        )
        res = calculate_training_week(inp)
        self.assertFalse(hasattr(res, "fitness_delta"))

    def test_balanced_plan_base_result(self):
        # Balanced plan: XP=8, sharpness=+2, morale=+1, readiness_delta=0.0
        inp = TrainingWeekInput(
            player_id="p1",
            age=20,
            overall=70,
            potential=80,
            sharpness=50,
            morale=75,
            current_readiness_modifier=1.00,
            plan_type="balanced",
            intensity="normal",
            is_injured=False,
            training_pitch_level=1,
        )
        res = calculate_training_week(inp)
        self.assertEqual(res.xp_earned, 8)
        self.assertEqual(res.sharpness_delta, 2)
        self.assertEqual(res.morale_delta, 1)
        self.assertEqual(res.readiness_modifier, 1.00)

    def test_fitness_plan_increases_readiness(self):
        # Fitness plan: XP=4, sharpness=+0, morale=+0, readiness_delta=+0.03
        inp = TrainingWeekInput(
            player_id="p1",
            age=20,
            overall=70,
            potential=80,
            sharpness=50,
            morale=75,
            current_readiness_modifier=1.00,
            plan_type="fitness",
            intensity="normal",
            is_injured=False,
            training_pitch_level=1,
        )
        res = calculate_training_week(inp)
        self.assertEqual(res.xp_earned, 4)
        self.assertEqual(res.sharpness_delta, 0)
        self.assertEqual(res.morale_delta, 0)
        self.assertEqual(res.readiness_modifier, 1.03)

    def test_sharpness_plan_reduces_morale(self):
        # Sharpness plan: XP=6, sharpness=+5, morale=-1, readiness_delta=+0.02
        inp = TrainingWeekInput(
            player_id="p1",
            age=20,
            overall=70,
            potential=80,
            sharpness=50,
            morale=75,
            current_readiness_modifier=1.00,
            plan_type="sharpness",
            intensity="normal",
            is_injured=False,
            training_pitch_level=1,
        )
        res = calculate_training_week(inp)
        self.assertEqual(res.xp_earned, 6)
        self.assertEqual(res.sharpness_delta, 5)
        self.assertEqual(res.morale_delta, -1)
        self.assertEqual(res.readiness_modifier, 1.02)

    def test_tactical_plan_gives_max_xp(self):
        # Tactical plan: XP=10, sharpness=+1, morale=+3, readiness_delta=+0.00
        inp = TrainingWeekInput(
            player_id="p1",
            age=20,
            overall=70,
            potential=80,
            sharpness=50,
            morale=75,
            current_readiness_modifier=1.00,
            plan_type="tactical",
            intensity="normal",
            is_injured=False,
            training_pitch_level=1,
        )
        res = calculate_training_week(inp)
        self.assertEqual(res.xp_earned, 10)
        self.assertEqual(res.sharpness_delta, 1)
        self.assertEqual(res.morale_delta, 3)
        self.assertEqual(res.readiness_modifier, 1.00)

    def test_heavy_intensity_increases_xp_reduces_morale_and_readiness(self):
        # Heavy intensity: XP mult=1.25, morale=-2, readiness=-0.02
        # Balanced + Heavy:
        # XP = 8 * 1.25 = 10
        # Sharpness = +2
        # Morale = 1 + (-2) = -1
        # Readiness = 1.00 + 0.00 - 0.02 = 0.98
        inp = TrainingWeekInput(
            player_id="p1",
            age=20,
            overall=70,
            potential=80,
            sharpness=50,
            morale=75,
            current_readiness_modifier=1.00,
            plan_type="balanced",
            intensity="heavy",
            is_injured=False,
            training_pitch_level=1,
        )
        res = calculate_training_week(inp)
        self.assertEqual(res.xp_earned, 10)
        self.assertEqual(res.sharpness_delta, 2)
        self.assertEqual(res.morale_delta, -1)
        self.assertEqual(res.readiness_modifier, 0.98)

    def test_light_intensity_reduces_xp_improves_morale_and_readiness(self):
        # Light intensity: XP mult=0.75, morale=+1, readiness=+0.01
        # Balanced + Light:
        # XP = 8 * 0.75 = 6
        # Sharpness = +2
        # Morale = 1 + 1 = 2
        # Readiness = 1.00 + 0.00 + 0.01 = 1.01
        inp = TrainingWeekInput(
            player_id="p1",
            age=20,
            overall=70,
            potential=80,
            sharpness=50,
            morale=75,
            current_readiness_modifier=1.00,
            plan_type="balanced",
            intensity="light",
            is_injured=False,
            training_pitch_level=1,
        )
        res = calculate_training_week(inp)
        self.assertEqual(res.xp_earned, 6)
        self.assertEqual(res.sharpness_delta, 2)
        self.assertEqual(res.morale_delta, 2)
        self.assertEqual(res.readiness_modifier, 1.01)

    def test_readiness_modifier_clamped_at_min_085(self):
        # Fitness plan with heavy intensity on low readiness (0.85):
        # Fitness Δ = +0.03, Heavy Δ = -0.02, Net = +0.01
        # Starting at 0.85 -> 0.86
        inp1 = TrainingWeekInput(
            player_id="p1",
            age=20,
            overall=70,
            potential=80,
            sharpness=50,
            morale=75,
            current_readiness_modifier=0.85,
            plan_type="fitness",
            intensity="heavy",
            is_injured=False,
            training_pitch_level=1,
        )
        res1 = calculate_training_week(inp1)
        self.assertEqual(res1.readiness_modifier, 0.86)

        # Tactical plan with heavy intensity on low readiness (0.85):
        # Tactical Δ = 0.0, Heavy Δ = -0.02. Net = -0.02
        # Starting at 0.85 -> 0.83, should be clamped to 0.85
        inp2 = TrainingWeekInput(
            player_id="p1",
            age=20,
            overall=70,
            potential=80,
            sharpness=50,
            morale=75,
            current_readiness_modifier=0.85,
            plan_type="tactical",
            intensity="heavy",
            is_injured=False,
            training_pitch_level=1,
        )
        res2 = calculate_training_week(inp2)
        self.assertEqual(res2.readiness_modifier, 0.85)

    def test_readiness_modifier_clamped_at_max_105(self):
        # Fitness plan with light intensity on high readiness (1.04):
        # Fitness Δ = +0.03, Light Δ = +0.01. Net = +0.04
        # Starting at 1.04 -> 1.08, should be clamped to 1.05
        inp = TrainingWeekInput(
            player_id="p1",
            age=20,
            overall=70,
            potential=80,
            sharpness=50,
            morale=75,
            current_readiness_modifier=1.04,
            plan_type="fitness",
            intensity="light",
            is_injured=False,
            training_pitch_level=1,
        )
        res = calculate_training_week(inp)
        self.assertEqual(res.readiness_modifier, 1.05)

    def test_injured_player_gets_no_xp(self):
        inp = TrainingWeekInput(
            player_id="p1",
            age=20,
            overall=70,
            potential=80,
            sharpness=50,
            morale=75,
            current_readiness_modifier=1.00,
            plan_type="balanced",
            intensity="normal",
            is_injured=True,
            training_pitch_level=1,
        )
        res = calculate_training_week(inp)
        self.assertEqual(res.xp_earned, 0)
        self.assertEqual(res.sharpness_delta, 0)

    def test_injured_player_gets_morale_penalty(self):
        inp = TrainingWeekInput(
            player_id="p1",
            age=20,
            overall=70,
            potential=80,
            sharpness=50,
            morale=75,
            current_readiness_modifier=1.00,
            plan_type="balanced",
            intensity="normal",
            is_injured=True,
            training_pitch_level=1,
        )
        res = calculate_training_week(inp)
        self.assertEqual(res.morale_delta, -1)

    def test_injured_player_readiness_unchanged(self):
        inp = TrainingWeekInput(
            player_id="p1",
            age=20,
            overall=70,
            potential=80,
            sharpness=50,
            morale=75,
            current_readiness_modifier=0.97,
            plan_type="balanced",
            intensity="normal",
            is_injured=True,
            training_pitch_level=1,
        )
        res = calculate_training_week(inp)
        self.assertEqual(res.readiness_modifier, 0.97)
        self.assertEqual(res.notes, ["Missed training (injured)"])

    def test_training_pitch_level_1_no_bonus(self):
        # Balanced: base XP = 8. Pitch level 1 -> +0 bonus XP
        inp = TrainingWeekInput(
            player_id="p1",
            age=20,
            overall=70,
            potential=80,
            sharpness=50,
            morale=75,
            current_readiness_modifier=1.00,
            plan_type="balanced",
            intensity="normal",
            is_injured=False,
            training_pitch_level=1,
        )
        res = calculate_training_week(inp)
        self.assertEqual(res.xp_earned, 8)

    def test_training_pitch_level_5_max_bonus(self):
        # Balanced: base XP = 8. Pitch level 5 -> +4 bonus XP. Total XP = 12
        inp = TrainingWeekInput(
            player_id="p1",
            age=20,
            overall=70,
            potential=80,
            sharpness=50,
            morale=75,
            current_readiness_modifier=1.00,
            plan_type="balanced",
            intensity="normal",
            is_injured=False,
            training_pitch_level=5,
        )
        res = calculate_training_week(inp)
        self.assertEqual(res.xp_earned, 12)

    def test_match_xp_formula_min_clamp(self):
        # 10 minutes played, rating = 4.0
        # base = 5
        # min_played / 30 = 10 // 30 = 0
        # rating diff = 4.0 - 6.0 = -2.0 -> rating bonus = -4
        # Total = 5 - 4 = 1 XP
        xp = calculate_match_development_xp(minutes_played=10, match_rating=4.0)
        self.assertEqual(xp, 1)

        # Extreme rating check (2.0)
        # base = 5
        # rating diff = 2.0 - 6.0 = -4.0 -> rating bonus = -8
        # Total = 5 - 8 = -3. Clamped to min = 1
        xp_low = calculate_match_development_xp(minutes_played=10, match_rating=2.0)
        self.assertEqual(xp_low, 1)

    def test_match_xp_formula_max_clamp(self):
        # 90 minutes played, rating = 10.0
        # base = 5
        # min_played / 30 = 90 // 30 = 3 -> +9
        # rating diff = 10.0 - 6.0 = 4.0 -> rating bonus = +8
        # Total = 5 + 9 + 8 = 22 XP. Clamped to max = 20
        xp = calculate_match_development_xp(minutes_played=90, match_rating=10.0)
        self.assertEqual(xp, 20)

    def test_match_xp_rating_bonus_positive(self):
        # 60 minutes played, rating = 7.5
        # base = 5
        # min_played / 30 = 60 // 30 = 2 -> +6
        # rating diff = 7.5 - 6.0 = 1.5 -> rating bonus = 1.5 * 2 = 3
        # Total = 5 + 6 + 3 = 14 XP
        xp = calculate_match_development_xp(minutes_played=60, match_rating=7.5)
        self.assertEqual(xp, 14)

    def test_match_xp_rating_penalty_negative(self):
        # 60 minutes played, rating = 5.5
        # base = 5
        # min_played / 30 = 60 // 30 = 2 -> +6
        # rating diff = 5.5 - 6.0 = -0.5 -> rating bonus = -0.5 * 2 = -1
        # Total = 5 + 6 - 1 = 10 XP
        xp = calculate_match_development_xp(minutes_played=60, match_rating=5.5)
        self.assertEqual(xp, 10)

    def test_season_bonus_uses_average_weekly_xp(self):
        # Weeks trained = 10. Total XP = 150. Avg = 15.0 (<16) -> bonus = 0
        bonus = calculate_season_training_bonus(
            age=22,
            overall=65,
            potential=80,
            training_xp=100,
            match_xp=50,
            weeks_trained=10,
            season_bonus_already_applied=False,
        )
        self.assertEqual(bonus, 0)

        # Weeks trained = 10. Total XP = 200. Avg = 20.0 (16-27) -> bonus = 1
        bonus_1 = calculate_season_training_bonus(
            age=22,
            overall=65,
            potential=80,
            training_xp=120,
            match_xp=80,
            weeks_trained=10,
            season_bonus_already_applied=False,
        )
        self.assertEqual(bonus_1, 1)

        # Weeks trained = 10. Total XP = 300. Avg = 30.0 (>=28) -> bonus = 2
        bonus_2 = calculate_season_training_bonus(
            age=22,
            overall=65,
            potential=80,
            training_xp=180,
            match_xp=120,
            weeks_trained=10,
            season_bonus_already_applied=False,
        )
        self.assertEqual(bonus_2, 2)

    def test_season_bonus_zero_for_age_30(self):
        # Even with high XP, if age is 30, bonus should be 0
        bonus = calculate_season_training_bonus(
            age=30,
            overall=65,
            potential=80,
            training_xp=180,
            match_xp=120,
            weeks_trained=10,
            season_bonus_already_applied=False,
        )
        self.assertEqual(bonus, 0)

    def test_season_bonus_zero_for_age_31(self):
        bonus = calculate_season_training_bonus(
            age=31,
            overall=65,
            potential=80,
            training_xp=180,
            match_xp=120,
            weeks_trained=10,
            season_bonus_already_applied=False,
        )
        self.assertEqual(bonus, 0)

    def test_season_bonus_zero_at_potential(self):
        # Overall equals potential -> bonus = 0
        bonus = calculate_season_training_bonus(
            age=22,
            overall=80,
            potential=80,
            training_xp=180,
            match_xp=120,
            weeks_trained=10,
            season_bonus_already_applied=False,
        )
        self.assertEqual(bonus, 0)

    def test_season_bonus_returns_one(self):
        # Avg weekly XP = (100 + 70) / 10 = 17.0 -> 1 OVR bonus
        bonus = calculate_season_training_bonus(
            age=25,
            overall=70,
            potential=75,
            training_xp=100,
            match_xp=70,
            weeks_trained=10,
            season_bonus_already_applied=False,
        )
        self.assertEqual(bonus, 1)

    def test_season_bonus_returns_two(self):
        # Avg weekly XP = (150 + 140) / 10 = 29.0 -> 2 OVR bonus
        bonus = calculate_season_training_bonus(
            age=25,
            overall=70,
            potential=75,
            training_xp=150,
            match_xp=140,
            weeks_trained=10,
            season_bonus_already_applied=False,
        )
        self.assertEqual(bonus, 2)

    def test_season_bonus_never_exceeds_potential_room(self):
        # Avg weekly XP = 30.0 -> raw bonus = 2. But overall is 74, potential is 75. Room is only 1.
        # Bonus should be clamped to 1.
        bonus = calculate_season_training_bonus(
            age=22,
            overall=74,
            potential=75,
            training_xp=180,
            match_xp=120,
            weeks_trained=10,
            season_bonus_already_applied=False,
        )
        self.assertEqual(bonus, 1)

    def test_season_bonus_zero_when_already_applied(self):
        # Already applied -> bonus = 0
        bonus = calculate_season_training_bonus(
            age=22,
            overall=65,
            potential=80,
            training_xp=180,
            match_xp=120,
            weeks_trained=10,
            season_bonus_already_applied=True,
        )
        self.assertEqual(bonus, 0)
