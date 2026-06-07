"""Background scheduler that periodically completes due bookings.

Runs the completion sweep on an interval (``BOOKING_COMPLETION_INTERVAL_MINUTES``)
inside the API process. A Redis lock ensures only one worker runs the sweep at a
time, so it stays safe behind gunicorn/uvicorn with multiple workers. Each tick
opens its own DB session and commits independently; failures are logged and
swallowed so a bad tick never kills the scheduler.
"""
from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.config import settings
from app.db.session import async_session_factory
from app.services import completion_service, lock_service

logger = logging.getLogger(__name__)

_LOCK_KEY = "scheduler:lock:booking-completion"
# TTL must comfortably exceed a single sweep; released in finally on the happy path.
_LOCK_TTL = 300


async def _run_completion_job(redis) -> None:
    owner = uuid.uuid4().hex
    try:
        got = await lock_service.acquire(redis, _LOCK_KEY, owner, ttl=_LOCK_TTL)
    except lock_service.LockCollisionError:
        # Another worker is running this tick — skip quietly.
        return
    except lock_service.RedisUnavailableError:
        logger.warning("Booking-completion tick skipped: Redis unavailable")
        return
    if not got:
        return

    try:
        async with async_session_factory() as db:
            count = await completion_service.complete_due_items(db, today=date.today())
            await db.commit()
        if count:
            logger.info("Booking-completion tick flipped %d item(s) to completed", count)
    except Exception:  # noqa: BLE001 — never let a bad tick kill the scheduler
        logger.exception("Booking-completion tick failed")
    finally:
        await lock_service.release(redis, _LOCK_KEY, owner)


def create_scheduler(redis) -> AsyncIOScheduler:
    """Build (but do not start) the completion scheduler bound to ``redis``."""
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        _run_completion_job,
        trigger="interval",
        minutes=settings.BOOKING_COMPLETION_INTERVAL_MINUTES,
        args=[redis],
        id="booking-completion",
        # Run shortly after boot so a freshly started server completes overdue
        # bookings without waiting a full interval.
        next_run_time=datetime.now(timezone.utc) + timedelta(seconds=30),
        max_instances=1,
        coalesce=True,
    )
    return scheduler
