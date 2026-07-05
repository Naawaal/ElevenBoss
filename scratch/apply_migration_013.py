import asyncio
import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

load_dotenv()

async def apply_migration():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL not found")
        return

    migration_file = "supabase/migrations/013_update_register_rpc.sql"
    if not os.path.exists(migration_file):
        print(f"Migration file {migration_file} does not exist")
        return

    with open(migration_file, "r") as f:
        sql = f.read()

    engine = create_async_engine(database_url)
    # The file has a single function definition, so we can run it as one block.
    async with engine.begin() as conn:
        print(f"Executing migration {migration_file}...")
        await conn.execute(text(sql))
        print("Migration applied successfully!")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(apply_migration())
