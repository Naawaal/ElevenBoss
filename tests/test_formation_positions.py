# tests/test_formation_positions.py

import unittest
from app.engine.formation_positions import FORMATION_COORDINATES, get_coordinates_for_formation

class TestFormationPositions(unittest.TestCase):
    def test_supported_formations_exist(self):
        supported = ["4-4-2", "4-3-3", "4-2-3-1", "3-5-2", "5-3-2"]
        for formation in supported:
            coords = get_coordinates_for_formation(formation)
            self.assertIsNotNone(coords)
            self.assertEqual(len(coords), 11)

    def test_coordinates_range(self):
        for formation, slots in FORMATION_COORDINATES.items():
            for slot, coord in slots.items():
                x, y = coord
                self.assertTrue(0 <= x <= 100, f"X coordinate {x} for {slot} in {formation} out of bounds.")
                self.assertTrue(0 <= y <= 100, f"Y coordinate {y} for {slot} in {formation} out of bounds.")

    def test_invalid_formation_raises(self):
        with self.assertRaises(ValueError):
            get_coordinates_for_formation("invalid-formation")
