"""APScheduler with **persistent** SQLAlchemy jobstore.

Jobs are idempotent: each job_id encodes (kind, user_id[, medication_id, time])
and replace_existing=True is used everywhere. After a restart we call
`sync_all()` which scans active medications/users and re-installs jobs that
disappeared while the process was down.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select

from app.config import get_settings
from app.db.models import Medication, User
from app.db.session import async_session_factory
from app.domain.enums import MedScheduleType, UserRole

log = logging.getLogger(__name__)
_scheduler: Optional[AsyncIOScheduler] = None


def get_scheduler() -> AsyncIOScheduler:
    if _scheduler is None:
        raise RuntimeError("Scheduler not initialized")
    return _scheduler


async def init_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    settings = get_settings()
    jobstores = {
        "default": SQLAlchemyJobStore(
            url=settings.database_url_sync, tablename="apscheduler_jobs"
        ),
    }
    _scheduler = AsyncIOScheduler(
        jobstores=jobstores,
        timezone=settings.tz,
        job_defaults={
            "coalesce": True,
            "misfire_grace_time": 600,
            "max_instances": 1,
        },
    )
    _scheduler.start()
    log.info("Scheduler started, tz=%s", settings.app_timezone)
    await sync_all()
    _install_recurring_watchdogs()
    await _install_greetings()
    return _scheduler


async def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None


def _install_recurring_watchdogs() -> None:
    s = get_scheduler()
    s.add_job(
        "app.scheduler.jobs:run_no_data_watchdog",
        trigger=CronTrigger(hour=10, minute=0),
        id="watchdog:no_data",
        replace_existing=True,
    )
    s.add_job(
        "app.scheduler.jobs:run_missed_med_watchdog",
        trigger=IntervalTrigger(minutes=15),
        id="watchdog:missed_med",
        replace_existing=True,
    )


_GREETING_SCHEDULE = {
    "morning":   (8,  0),
    "afternoon": (15, 0),
    "evening":   (21, 0),
}


async def _install_greetings() -> None:
    """Schedule morning/afternoon/evening greetings for every active patient."""
    s = get_scheduler()
    async with async_session_factory() as session:
        users = (await session.execute(
            select(User).where(User.role == UserRole.PATIENT, User.deleted_at.is_(None))
        )).scalars().all()
        for user in users:
            _add_greeting_jobs(s, user)
    log.info("Greetings installed for %d patients", len(users))


def _add_greeting_jobs(s: AsyncIOScheduler, user: User) -> None:
    for period, (hour, minute) in _GREETING_SCHEDULE.items():
        s.add_job(
            "app.scheduler.jobs:fire_greeting",
            trigger=CronTrigger(hour=hour, minute=minute, timezone=user.timezone),
            args=[user.telegram_id, period],
            id=f"greeting:{period}:{user.id}",
            replace_existing=True,
        )


def schedule_greetings(user: User) -> None:
    """(Re-)install all greeting jobs for one user — call on registration or TZ change."""
    _add_greeting_jobs(get_scheduler(), user)


def unschedule_greetings(user_id: int) -> None:
    """Remove all greeting jobs for a user (e.g. on account deletion)."""
    s = get_scheduler()
    for period in _GREETING_SCHEDULE:
        try:
            s.remove_job(f"greeting:{period}:{user_id}")
        except Exception:
            pass


# ----- per-medication scheduling -----
def _med_job_id(med_id: int, key: str) -> str:
    return f"med:{med_id}:{key}"


async def schedule_medication(med: Medication, user: User) -> None:
    """Replace all reminders for this medication with a fresh, deduplicated set."""
    s = get_scheduler()
    # purge previous jobs for this medication
    for job in s.get_jobs():
        if job.id.startswith(f"med:{med.id}:"):
            s.remove_job(job.id)

    if not med.is_active or med.schedule_type == MedScheduleType.AS_NEEDED:
        return

    if med.schedule_type == MedScheduleType.FIXED_TIMES:
        for t in med.schedule_data.get("times", []):
            hh, mm = (int(x) for x in t.split(":"))
            s.add_job(
                "app.scheduler.jobs:fire_med_reminder",
                trigger=CronTrigger(hour=hh, minute=mm, timezone=user.timezone),
                args=[user.telegram_id, med.id, t],
                id=_med_job_id(med.id, f"fix-{t}"),
                replace_existing=True,
            )
    elif med.schedule_type == MedScheduleType.EVERY_N_HOURS:
        interval = int(med.schedule_data.get("interval_hours", 8))
        anchor = med.schedule_data.get("anchor", "08:00")
        hh, mm = (int(x) for x in anchor.split(":"))
        s.add_job(
            "app.scheduler.jobs:fire_med_reminder",
            trigger=CronTrigger(
                hour=f"{hh}/{interval}", minute=mm, timezone=user.timezone
            ),
            args=[user.telegram_id, med.id, anchor],
            id=_med_job_id(med.id, "interval"),
            replace_existing=True,
        )


def unschedule_medication(med_id: int) -> None:
    s = get_scheduler()
    for job in s.get_jobs():
        if job.id.startswith(f"med:{med_id}:"):
            s.remove_job(job.id)


# ----- per-user watchdogs -----
def schedule_user_watchdogs(user: User) -> None:
    """Currently the watchdogs are global (cron-based), so this is a no-op
    placeholder for future per-user scheduling (e.g. nightly digests)."""
    return None


async def sync_all() -> None:
    """Reconcile DB → scheduler state."""
    async with async_session_factory() as session:
        meds = (await session.execute(
            select(Medication).where(Medication.is_active.is_(True))
        )).scalars().all()
        user_ids = {m.user_id for m in meds}
        users = (await session.execute(
            select(User).where(User.id.in_(user_ids))
        )).scalars().all() if user_ids else []
        users_by_id = {u.id: u for u in users}
        for med in meds:
            user = users_by_id.get(med.user_id)
            if user:
                await schedule_medication(med, user)
    log.info("Scheduler sync_all complete")
