"""
Database models and connection logic.

Note:
For a highly scalable, weightless Discord bot (antigravity architecture),
it is recommended to use:
  - PostgreSQL as the primary database
  - asyncpg or SQLAlchemy (async) for non-blocking I/O
  - PgBouncer in front of PostgreSQL to prevent connection exhaustion
  - Redis for caching guild/user profiles and config to minimize DB hits
"""
