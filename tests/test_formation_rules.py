# tests/test_formation_rules.py

import unittest
from app.engine.formation_rules import SUPPORTED_FORMATIONS, get_slots_for_formation, get_slot_rules

class TestFormationRules(unittest.TestCase):
    def test_supported_formations_have_11_slots(self):
        for form in SUPPORTED_FORMATIONS:
            slots = get_slots_for_formation(form)
            self.assertEqual(len(slots), 11, f"Formation {form} does not have exactly 11 slots.")
            
    def test_unsupported_formation_rejected(self):
        with self.assertRaises(ValueError):
            get_slots_for_formation("4-2-4")
            
    def test_slot_rules_validity(self):
        # GK slot should only allow GK as natural
        gk_rules = get_slot_rules("GK")
        self.assertEqual(gk_rules["natural"], ["GK"])
        self.assertEqual(gk_rules["compatible"], [])
        
        # LB slot should allow LB as natural, and LWB/CB as compatible
        lb_rules = get_slot_rules("LB")
        self.assertIn("LB", lb_rules["natural"])
        self.assertIn("LWB", lb_rules["compatible"])
        self.assertIn("CB", lb_rules["compatible"])

if __name__ == "__main__":
    unittest.main()
