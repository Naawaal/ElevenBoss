import unittest
import uuid
from app.engine.player_generator import generate_squad, POSITIONS_DISTRIBUTION
from app.models.player import Player

class TestPlayerGenerator(unittest.TestCase):
    def test_squad_generation(self):
        guild_id = "12345678"
        club_id = uuid.uuid4()
        
        squad = generate_squad(guild_id, club_id)
        
        # Generated squad has exactly 25 players
        self.assertEqual(len(squad), 25)
        
        # Position counts
        positions = [p.position for p in squad]
        expected_positions = sorted(POSITIONS_DISTRIBUTION)
        self.assertEqual(sorted(positions), expected_positions)
        
        # Average overall rating check (around 60-66)
        avg_ovr = sum(p.overall for p in squad) / len(squad)
        self.assertTrue(58 <= avg_ovr <= 66, f"Average OVR is {avg_ovr}, expected 58-66")
        
        for player in squad:
            self.assertIsInstance(player, Player)
            
            # Attributes validation
            self.assertEqual(player.guild_id, guild_id)
            self.assertEqual(player.club_id, club_id)
            self.assertTrue(player.first_name)
            self.assertTrue(player.last_name)
            self.assertTrue(player.display_name)
            self.assertEqual(player.display_name, f"{player.first_name} {player.last_name}")
            
            # Overall & Potential
            self.assertTrue(48 <= player.overall <= 78)
            self.assertTrue(player.overall <= player.potential <= 88)
            
            # Age ranges
            self.assertTrue(18 <= player.age <= 36)
            
            # Value & Wage
            self.assertTrue(player.value >= 0)
            self.assertTrue(player.wage >= 0)
            
            # Status
            self.assertEqual(player.fitness, 100)
            self.assertEqual(player.sharpness, 50)
            self.assertEqual(player.morale, 75)
            self.assertIn(player.preferred_foot, ["Left", "Right"])
            self.assertTrue(1 <= player.weak_foot <= 5)
            self.assertTrue(1 <= player.skill_moves <= 5)
            
            # Traits
            self.assertIsInstance(player.traits, dict)
            self.assertIn("list", player.traits)
            traits_list = player.traits["list"]
            self.assertIsInstance(traits_list, list)
            self.assertTrue(len(traits_list) <= 2)
            for trait in traits_list:
                self.assertIsInstance(trait, str)

if __name__ == "__main__":
    unittest.main()
