import unittest

class TestModelsImport(unittest.TestCase):
    def test_import_models(self):
        """Verify that all models import successfully and register in Base metadata."""
        from app.db.base import Base
        import app.models  # Trigger import and registration

        expected_tables = {
            "guild_configs",
            "managers",
            "leagues",
            "seasons",
            "clubs",
            "players",
            "lineups",
            "lineup_players",
            "fixtures",
            "match_results",
            "match_events",
            "league_standings",
            "scheduler_runs",
        }

        # Check metadata tables
        metadata_tables = set(Base.metadata.tables.keys())
        for table in expected_tables:
            self.assertIn(table, metadata_tables, f"Table '{table}' was not found in Base.metadata.")

if __name__ == "__main__":
    unittest.main()
