import random
import time
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.models.search_schedule import SCHEDULE_ROW_ID, SearchSchedule

# Selectable schedules and their period in seconds. "off" disables the job.
SCHEDULE_PERIODS: dict[str, int] = {
    "daily": 86_400,
    "weekly": 604_800,
}
SCHEDULE_OPTIONS: list[str] = ["off", *SCHEDULE_PERIODS]


def compute_next_run(now: float, period: int, *, first: bool) -> float:
    """Return the next run time (epoch seconds) at a randomized offset.

    ``first`` (just enabled / no prior run) picks a random moment within the
    next period. Otherwise the offset jitters around a full period so runs
    happen ~once per period but at a fresh random time each period — and at a
    random phase across installs, avoiding a thundering herd on Radarr/indexers.
    """
    if first:
        return now + random.uniform(0, period)
    return now + random.uniform(0.5, 1.5) * period


class SearchScheduleService:
    """Read/update the single search-schedule row."""

    def __init__(
        self, session: Session, *, clock: Callable[[], float] = time.time
    ) -> None:
        self._session = session
        self._clock = clock

    def get(self) -> SearchSchedule:
        """Return the schedule row, creating a default ("off") one if absent."""
        row = self._session.get(SearchSchedule, SCHEDULE_ROW_ID)
        if row is None:
            row = SearchSchedule(id=SCHEDULE_ROW_ID, schedule="off")
            self._session.add(row)
            self._session.commit()
        return row

    def set_schedule(self, value: str) -> SearchSchedule:
        """Set the schedule; recompute ``next_run_at`` only on a real change.

        Switching to "off" clears the timer. Re-saving the same value leaves the
        existing ``next_run_at`` untouched so saving the settings form doesn't
        keep pushing the next run back.
        """
        value = value if value in SCHEDULE_OPTIONS else "off"
        row = self.get()
        if value == row.schedule:
            return row
        row.schedule = value
        if value == "off":
            row.next_run_at = None
        else:
            row.next_run_at = compute_next_run(
                self._clock(), SCHEDULE_PERIODS[value], first=True
            )
        self._session.commit()
        return row

    def record_run(self, *, run_at: float, next_run_at: float | None, result: str) -> None:
        """Persist the outcome of a scheduled run and the next scheduled run."""
        row = self.get()
        row.last_run_at = run_at
        row.last_result = result
        row.next_run_at = next_run_at
        self._session.commit()

    def record_manual_run(self, *, run_at: float, result: str) -> None:
        """Record a manually triggered run, leaving ``next_run_at`` untouched."""
        row = self.get()
        row.last_run_at = run_at
        row.last_result = result
        self._session.commit()
