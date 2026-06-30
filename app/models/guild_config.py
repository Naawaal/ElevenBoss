import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Boolean, DateTime
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
    matchday_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        onupdate=func.now(), 
        nullable=False
    )
