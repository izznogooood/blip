"""Background scheduler for the recurring Radarr "Search Missing Movies" job.

Single-process uvicorn (see the Dockerfile — no ``--workers``) means one in-app
asyncio task is enough; no external scheduler dependency is needed. The loop is
started/cancelled by the FastAPI lifespan in ``app/main.py``.
"""

import asyncio
import logging
import time

import httpx

from app.clients.radarr_client import RadarrClient
from app.core.database import SessionLocal
from app.services.radarr_service import RadarrService
from app.services.search_schedule_service import (
    SCHEDULE_PERIODS,
    SearchScheduleService,
    compute_next_run,
)
from app.services.settings_service import SettingsService

logger = logging.getLogger(__name__)

# How often the loop wakes to check whether a run is due.
CHECK_INTERVAL_SECONDS = 60


def due_action(session, *, now: float) -> str:
    """Run one scheduling tick against ``session``; return a short status.

    Pure of any live loop/sleep so it can be unit-tested directly. When a run is
    due and Radarr is configured, this triggers ``MissingMoviesSearch``
    synchronously and records the outcome, then schedules the next run.
    """
    sched = SearchScheduleService(session)
    row = sched.get()

    if row.schedule not in SCHEDULE_PERIODS:
        return "off"
    period = SCHEDULE_PERIODS[row.schedule]

    if row.next_run_at is None:
        # Enabled but never scheduled (e.g. set via env/DB directly): arm it.
        row.next_run_at = compute_next_run(now, period, first=True)
        session.commit()
        return "scheduled"

    if now < row.next_run_at:
        return "waiting"

    # Due. Compute the following run up front so we advance even on failure and
    # don't retry every tick.
    next_run = compute_next_run(now, period, first=False)
    resolved = SettingsService(session).resolve()
    if not resolved.radarr_configured:
        sched.record_run(run_at=now, next_run_at=next_run, result="skipped: no Radarr")
        return "skipped"

    result = "ok"
    try:
        RadarrService(
            RadarrClient(resolved.radarr_base_url, resolved.radarr_api_key)
        ).search_missing()
    except httpx.HTTPError as exc:
        result = f"error: {type(exc).__name__}"
        logger.warning("Scheduled Radarr search failed: %s", type(exc).__name__)
    sched.record_run(run_at=now, next_run_at=next_run, result=result)
    return result


def _tick_once() -> None:
    with SessionLocal() as session:
        due_action(session, now=time.time())


async def run_scheduler() -> None:
    """Loop forever, running a tick every ``CHECK_INTERVAL_SECONDS``.

    Cancel-safe: cancellation propagates out cleanly on shutdown. The sync tick
    (which may do blocking HTTP) is offloaded to a thread so the event loop is
    never blocked.
    """
    logger.info("Search scheduler started")
    try:
        while True:
            try:
                await asyncio.to_thread(_tick_once)
            except Exception:  # never let one bad tick kill the loop
                logger.exception("Scheduler tick failed")
            await asyncio.sleep(CHECK_INTERVAL_SECONDS)
    except asyncio.CancelledError:
        logger.info("Search scheduler stopped")
        raise
