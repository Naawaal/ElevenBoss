import uuid
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.db.base import Base

class SeasonSnapshot(Base):
    __tablename__ = "season_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    guild_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    season_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False, index=True)
    league_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False, index=True)
    season_number: Mapped[int] = mapped_column(Integer, nullable=False)
    champion_club_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("clubs.id", ondelete="SET NULL"), nullable=True)
    runner_up_club_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("clubs.id", ondelete="SET NULL"), nullable=True)
    final_table_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    total_matches: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_goals: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    season: Mapped["Season"] = relationship("Season")
    league: Mapped["League"] = relationship("League")
    champion_club: Mapped["Club"] = relationship("Club", foreign_keys=[champion_club_id])
    runner_up_club: Mapped["Club"] = relationship("Club", foreign_keys=[runner_up_club_id])
