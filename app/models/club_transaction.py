# app/models/club_transaction.py

import uuid
from datetime import datetime
from sqlalchemy import String, ForeignKey, BigInteger, DateTime, JSON, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.db.base import Base

class ClubTransaction(Base):
    __tablename__ = "club_transactions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    club_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clubs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    guild_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[str] = mapped_column(String(128), nullable=False)

    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)

    balance_before: Mapped[int] = mapped_column(BigInteger, nullable=False)
    balance_after: Mapped[int] = mapped_column(BigInteger, nullable=False)

    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    metadata_json: Mapped[dict | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    club: Mapped["Club"] = relationship("Club", foreign_keys=[club_id])

    __table_args__ = (
        UniqueConstraint(
            "club_id",
            "source_type",
            "source_id",
            name="uq_club_transaction_source",
        ),
    )
