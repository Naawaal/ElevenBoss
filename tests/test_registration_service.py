import unittest
from app.services.registration_service import validate_club_name

class TestRegistrationService(unittest.TestCase):
    def test_validate_club_name_success(self):
        # Normal football club name
        self.assertEqual(validate_club_name("Kathmandu FC"), "Kathmandu FC")
        
        # Hyphens and apostrophes
        self.assertEqual(validate_club_name("West-Ham United"), "West-Ham United")
        self.assertEqual(validate_club_name("O'Connor City"), "O'Connor City")
        
        # Collapses extra whitespace
        self.assertEqual(validate_club_name("  Kathmandu    FC  "), "Kathmandu FC")

    def test_validate_club_name_failures(self):
        # Empty/None names
        with self.assertRaises(ValueError):
            validate_club_name("")
            
        with self.assertRaises(ValueError):
            validate_club_name("   ")

        # Too short names
        with self.assertRaises(ValueError):
            validate_club_name("FC")

        # Too long names
        with self.assertRaises(ValueError):
            validate_club_name("A" * 33)

        # Blocked mass mentions
        with self.assertRaises(ValueError):
            validate_club_name("Club @everyone")
            
        with self.assertRaises(ValueError):
            validate_club_name("Club @here")

        # Blocked URLs
        with self.assertRaises(ValueError):
            validate_club_name("http://club.com")
            
        with self.assertRaises(ValueError):
            validate_club_name("www.myclub.org")
            
        with self.assertRaises(ValueError):
            validate_club_name("MyClub.com")

        # Invalid characters (e.g. symbols)
        with self.assertRaises(ValueError):
            validate_club_name("Kathmandu FC!")
            
        with self.assertRaises(ValueError):
            validate_club_name("Kathmandu FC?")

if __name__ == "__main__":
    unittest.main()
