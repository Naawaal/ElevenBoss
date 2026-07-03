import uuid
from datetime import datetime
from sqlalchemy import String, Integer, BigInteger, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.db.base import Base

class Club(Base):
    __tablename__ = "clubs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    guild_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    league_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("leagues.id", ondelete="SET NULL"), nullable=True, index=True)
    season_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("seasons.id", ondelete="SET NULL"), nullable=True, index=True)
    manager_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("managers.id", ondelete="SET NULL"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    # Casefold + whitespace-normalized version of name; used for uniqueness checks
    normalized_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    short_name: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_bot_controlled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    budget: Mapped[int] = mapped_column(BigInteger, default=400_000, nullable=False)
    reputation: Mapped[int] = mapped_column(Integer, default=500, nullable=False)
    stadium_capacity: Mapped[int] = mapped_column(Integer, default=10000, nullable=False)
    overall_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        onupdate=func.now(), 
        nullable=False
    )

    # Relationships
    league: Mapped["League"] = relationship("League", back_populates="clubs", foreign_keys=[league_id])
    manager: Mapped["Manager"] = relationship(
        "Manager", 
        back_populates="club", 
        uselist=False, 
        foreign_keys=[manager_id]
    )
    players: Mapped[list["Player"]] = relationship(
        "Player", 
        back_populates="club", 
        cascade="all, delete-orphan",
        foreign_keys="Player.club_id"
    )
    home_fixtures: Mapped[list["Fixture"]] = relationship(
        "Fixture", 
        back_populates="home_club",
        foreign_keys="Fixture.home_club_id"
    )
    away_fixtures: Mapped[list["Fixture"]] = relationship(
        "Fixture", 
        back_populates="away_club",
        foreign_keys="Fixture.away_club_id"
    )
    lineups: Mapped[list["Lineup"]] = relationship(
        "Lineup", 
        back_populates="club", 
        cascade="all, delete-orphan"
    )
    facilities: Mapped[list["Facility"]] = relationship(
        "Facility",
        back_populates="club",
        cascade="all, delete-orphan",
        foreign_keys="Facility.club_id"
    )

    __table_args__ = (
        UniqueConstraint("guild_id", "name", name="uq_club_guild_name"),
        UniqueConstraint("guild_id", "normalized_name", name="uq_club_guild_normalized_name"),
    )
