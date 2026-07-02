# app/models/guild_config.py

import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Boolean, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.db.base import Base

class GuildConfig(Base):
    __tablename__ = "guild_configs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    guild_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    game_channel_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    admin_role_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    default_league_size: Mapped[int] = mapped_column(Integer, default=8, nullable=False)
    
    # Automation Configurations
    auto_join_draft_league: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    auto_start_league: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    auto_fill_with_bot_clubs: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    minimum_human_clubs: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    registration_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Matchday Schedule Configurations
    matchday_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    matchday_day: Mapped[str | None] = mapped_column(String(32), nullable=True)
    matchday_time: Mapped[str | None] = mapped_column(String(32), nullable=True)
    matchday_timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kathmandu", nullable=False)
    matchday_announcement_channel_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    
    # Onboarding / Thread Configuration
    # NULL = unknown, TRUE = private threads worked before, FALSE = use public fallback
    supports_private_threads: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # Automation Status Metrics
    automation_status: Mapped[str] = mapped_column(String(32), default="idle", nullable=False)
    last_automation_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_automation_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_automation_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        onupdate=func.now(), 
        nullable=False
    )
