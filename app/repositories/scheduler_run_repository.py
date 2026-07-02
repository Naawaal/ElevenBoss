# app/repositories/scheduler_run_repository.py

from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.scheduler_run import SchedulerRun, SchedulerRunStatus

async def create_running_job(
    session: AsyncSession,
    job_key: str,
    job_type: str,
    guild_id: int | str | None = None,
    metadata: dict | None = None
) -> SchedulerRun:
    """
    Creates a new running job in scheduler_runs.
    """
    job = SchedulerRun(
        guild_id=str(guild_id) if guild_id is not None else None,
        job_key=job_key,
        job_type=job_type,
        status=SchedulerRunStatus.RUNNING,
        started_at=datetime.utcnow(),
        run_metadata=metadata
    )
    session.add(job)
    return job

async def mark_job_success(
    session: AsyncSession,
    job_key: str
) -> None:
    """
    Mark a scheduler job as successful.
    """
    stmt = select(SchedulerRun).where(SchedulerRun.job_key == job_key)
    result = await session.execute(stmt)
    job = result.scalar_one_or_none()
    if job:
        job.status = SchedulerRunStatus.SUCCESS
        job.finished_at = datetime.utcnow()

async def mark_job_failed(
    session: AsyncSession,
    job_key: str,
    error: str
) -> None:
    """
    Mark a scheduler job as failed with the error traceback.
    """
    stmt = select(SchedulerRun).where(SchedulerRun.job_key == job_key)
    result = await session.execute(stmt)
    job = result.scalar_one_or_none()
    if job:
        job.status = SchedulerRunStatus.FAILED
        job.finished_at = datetime.utcnow()
        job.error = error

async def get_job_by_key(
    session: AsyncSession,
    job_key: str
) -> SchedulerRun | None:
    """
    Retrieves a scheduler run by its job key.
    """
    stmt = select(SchedulerRun).where(SchedulerRun.job_key == job_key)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()

async def get_or_create_running_job(
    session: AsyncSession,
    job_key: str,
    job_type: str,
    guild_id: int | str | None = None,
    metadata: dict | None = None
) -> SchedulerRun:
    """
    Locks and retrieves a scheduler run by key.
    - If found and RUNNING/SUCCESS: raises ValueError.
    - If found and FAILED/SKIPPED: resets status to RUNNING and clears completion details.
    - If not found: inserts a new RUNNING record.
    """
    stmt = select(SchedulerRun).where(SchedulerRun.job_key == job_key).with_for_update()
    result = await session.execute(stmt)
    job = result.scalar_one_or_none()
    
    if job:
        if job.status == SchedulerRunStatus.RUNNING:
            raise ValueError("Job already in progress.")
        if job.status == SchedulerRunStatus.SUCCESS:
            raise ValueError("Job already completed successfully.")
            
        # Reset and reuse
        job.status = SchedulerRunStatus.RUNNING
        job.started_at = datetime.utcnow()
        job.finished_at = None
        job.error = None
        job.run_metadata = metadata
        return job
    else:
        new_job = SchedulerRun(
            guild_id=str(guild_id) if guild_id is not None else None,
            job_key=job_key,
            job_type=job_type,
            status=SchedulerRunStatus.RUNNING,
            started_at=datetime.utcnow(),
            run_metadata=metadata
        )
        session.add(new_job)
        return new_job
