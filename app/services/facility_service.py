# app/services/facility_service.py

import logging
import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.club import Club
from app.models.facility import Facility, FacilityType, FacilityStatus
from app.config import config

logger = logging.getLogger("app.services.facility_service")

class FacilityService:
    @staticmethod
    async def ensure_default_facilities(session: AsyncSession, club_id: uuid.UUID) -> list[Facility]:
        """
        Ensures a club has all 5 default facilities initialized at level 1.
        Returns the complete list of facilities for the club.
        """
        # Fetch existing facilities
        stmt = select(Facility).where(Facility.club_id == club_id)
        res = await session.execute(stmt)
        existing = {f.facility_type: f for f in res.scalars().all()}

        facilities_list = []
        created_any = False

        for f_type in FacilityType:
            if f_type not in existing:
                # Initialize new facility
                new_fac = Facility(
                    club_id=club_id,
                    facility_type=f_type,
                    level=1,
                    status=FacilityStatus.IDLE
                )
                session.add(new_fac)
                facilities_list.append(new_fac)
                created_any = True
                logger.info(f"Initialized facility {f_type.value} at level 1 for club {club_id}")
            else:
                facilities_list.append(existing[f_type])

        if created_any:
            await session.flush()

        return facilities_list

    @staticmethod
    async def start_upgrade(
        session: AsyncSession,
        club_id: uuid.UUID,
        facility_type: FacilityType,
        now_utc: datetime | None = None
    ) -> Facility:
        """
        Starts the upgrade process for a facility:
        - Locks the club and facility rows for updates.
        - Validates that the facility is not already at max level.
        - Validates that the facility is not already upgrading.
        - Validates that no other facility is currently upgrading.
        - Deducts the upgrade cost from the club's budget.
        - Sets the upgrade status and completion time.
        """
        if now_utc is None:
            now_utc = datetime.utcnow()
        if now_utc.tzinfo is None:
            now_utc = now_utc.replace(tzinfo=timezone.utc)

        # 1. Lock the club row to prevent concurrent budget mutations
        club_stmt = select(Club).where(Club.id == club_id).with_for_update()
        club_res = await session.execute(club_stmt)
        club = club_res.scalar_one_or_none()
        if not club:
            raise ValueError("Club not found")

        # 2. Lock the specific facility row
        fac_stmt = select(Facility).where(
            and_(
                Facility.club_id == club_id,
                Facility.facility_type == facility_type
            )
        ).with_for_update()
        fac_res = await session.execute(fac_stmt)
        facility = fac_res.scalar_one_or_none()
        if not facility:
            raise ValueError(f"Facility of type {facility_type.value} not found for this club")

        # 3. Validation: Max Level
        if facility.level >= config.FACILITY_MAX_LEVEL:
            raise ValueError(f"{facility_type.value.replace('_', ' ').title()} is already at the maximum level")

        # 4. Validation: Already Upgrading
        if facility.status == FacilityStatus.UPGRADING:
            raise ValueError(f"{facility_type.value.replace('_', ' ').title()} is already undergoing an upgrade")

        # 5. Validation: Single active upgrade limit
        other_stmt = select(Facility).where(
            and_(
                Facility.club_id == club_id,
                Facility.status == FacilityStatus.UPGRADING
            )
        )
        other_res = await session.execute(other_stmt)
        if other_res.scalars().first() is not None:
            raise ValueError("Another facility is already upgrading. Only one upgrade can be active at a time.")

        # 6. Budget Check
        cost = config.FACILITY_UPGRADE_COSTS.get(facility.level)
        if cost is None:
            raise ValueError(f"Invalid upgrade configuration for level {facility.level}")

        if club.budget < cost:
            raise ValueError(f"Insufficient funds to upgrade {facility_type.value.replace('_', ' ').title()}. Cost: {cost:,}, Budget: {club.budget:,}")

        duration_hours = config.FACILITY_UPGRADE_DURATIONS_HOURS.get(facility.level, 0)

        # 7. Deduct budget and start upgrade
        club.budget -= cost
        facility.status = FacilityStatus.UPGRADING
        facility.upgrade_started_at = now_utc
        facility.upgrade_completes_at = now_utc + timedelta(hours=duration_hours)

        await session.flush()
        logger.info(f"Started upgrade for {facility_type.value} to level {facility.level + 1} for club {club.name}")
        return facility
