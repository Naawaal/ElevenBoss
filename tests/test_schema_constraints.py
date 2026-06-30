import unittest
from sqlalchemy import UniqueConstraint, Index, CheckConstraint

class TestSchemaConstraints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.db.base import Base
        import app.models  # Ensure registration
        cls.metadata = Base.metadata

    def test_manager_unique_constraints(self):
        table = self.metadata.tables["managers"]
        unique_columns = []
        for c in table.constraints:
            if isinstance(c, UniqueConstraint):
                unique_columns.append(set(col.name for col in c.columns))
        
        self.assertIn({"guild_id", "discord_user_id"}, unique_columns)

    def test_league_unique_constraints(self):
        table = self.metadata.tables["leagues"]
        unique_columns = []
        for c in table.constraints:
            if isinstance(c, UniqueConstraint):
                unique_columns.append(set(col.name for col in c.columns))
        
        self.assertIn({"guild_id", "name"}, unique_columns)

    def test_season_unique_constraints(self):
        table = self.metadata.tables["seasons"]
        unique_columns = []
        for c in table.constraints:
            if isinstance(c, UniqueConstraint):
                unique_columns.append(set(col.name for col in c.columns))
        
        self.assertIn({"league_id", "season_number"}, unique_columns)

    def test_club_unique_constraints(self):
        table = self.metadata.tables["clubs"]
        unique_columns = []
        for c in table.constraints:
            if isinstance(c, UniqueConstraint):
                unique_columns.append(set(col.name for col in c.columns))
        
        self.assertIn({"guild_id", "name"}, unique_columns)

    def test_fixture_unique_constraints(self):
        table = self.metadata.tables["fixtures"]
        unique_columns = []
        for c in table.constraints:
            if isinstance(c, UniqueConstraint):
                unique_columns.append(set(col.name for col in c.columns))
        
        self.assertIn({"season_id", "week", "home_club_id", "away_club_id"}, unique_columns)

    def test_standing_unique_constraints(self):
        table = self.metadata.tables["league_standings"]
        unique_columns = []
        for c in table.constraints:
            if isinstance(c, UniqueConstraint):
                unique_columns.append(set(col.name for col in c.columns))
        
        self.assertIn({"season_id", "club_id"}, unique_columns)

    def test_scheduler_runs_unique_constraints(self):
        table = self.metadata.tables["scheduler_runs"]
        # Can be either UniqueConstraint or unique=True on job_key column
        job_key_col = table.c["job_key"]
        has_unique_constraint = job_key_col.unique or any(
            isinstance(c, UniqueConstraint) and "job_key" in [col.name for col in c.columns]
            for c in table.constraints
        )
        self.assertTrue(has_unique_constraint, "job_key must be unique")

    def test_player_indexes_and_checks(self):
        table = self.metadata.tables["players"]
        indexed_cols = {col.name for col in table.columns if col.index}
        # Also check explicit indexes
        for idx in table.indexes:
            for col in idx.columns:
                indexed_cols.add(col.name)

        # Requirements: guild_id, club_id, position, overall, and potential
        self.assertIn("guild_id", indexed_cols)
        self.assertIn("club_id", indexed_cols)
        self.assertIn("position", indexed_cols)
        self.assertIn("overall", indexed_cols)
        self.assertIn("potential", indexed_cols)

        # CheckConstraints check
        check_names = {c.name for c in table.constraints if isinstance(c, CheckConstraint)}
        self.assertIn("chk_player_preferred_foot", check_names)
        self.assertIn("chk_player_weak_foot", check_names)
        self.assertIn("chk_player_skill_moves", check_names)
        self.assertIn("chk_player_position", check_names)

    def test_lineups_active_partial_index(self):
        table = self.metadata.tables["lineups"]
        index_names = {idx.name: idx for idx in table.indexes}
        self.assertIn("uq_active_lineup", index_names)
        
        idx = index_names["uq_active_lineup"]
        self.assertTrue(idx.unique)
        self.assertEqual(idx.dialect_options["postgresql"]["where"], "is_active = true")

if __name__ == "__main__":
    unittest.main()
