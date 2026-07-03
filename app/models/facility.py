# app/models/facility.py

import uuid
import enum
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, ForeignKey, Enum, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.db.base import Base

class FacilityType(str, enum.Enum):
    STADIUM = "stadium"
    TRAINING_PITCH = "training_pitch"
    YOUTH_ACADEMY = "youth_academy"
    MEDICAL_CLINIC = "medical_clinic"
    CLUB_HQ = "club_hq"

class FacilityStatus(str, enum.Enum):
    IDLE = "IDLE"
    UPGRADING = "UPGRADING"
    MAX_LEVEL = "MAX_LEVEL"

class Facility(Base):
    __tablename__ = "facilities"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    club_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False, index=True)
    facility_type: Mapped[FacilityType] = mapped_column(
        Enum(FacilityType, name="facility_type", values_callable=lambda obj: [item.value for item in obj]),
        nullable=False
    )
    level: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[FacilityStatus] = mapped_column(
        Enum(FacilityStatus, name="facility_status", values_callable=lambda obj: [item.value for item in obj]),
        default=FacilityStatus.IDLE,
        nullable=False
    )
    upgrade_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    upgrade_completes_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

    # Relationships
    club: Mapped["Club"] = relationship("Club", back_populates="facilities", foreign_keys=[club_id])

    __table_args__ = (
        UniqueConstraint("club_id", "facility_type", name="uq_club_facility_type"),
    )
