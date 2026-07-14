import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base
from app.models.search_schedule import SearchSchedule  # noqa: F401  registers table
from app.schemas.settings import ResolvedSettings
from app.services import scheduler
from app.services.radarr_service import RadarrService
from app.services.search_schedule_service import SearchScheduleService
from app.services.settings_service import SettingsService

DAY = 86_400


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as s:
        yield s


@pytest.fixture(autouse=True)
def _fake_radarr(monkeypatch):
    """Record search_missing calls instead of hitting a live Radarr."""
    calls: list[bool] = []
    monkeypatch.setattr(
        RadarrService, "search_missing", lambda self: calls.append(True)
    )
    return calls


def _configure(monkeypatch, *, configured: bool) -> None:
    resolved = ResolvedSettings(
        radarr_base_url="http://radarr" if configured else None,
        radarr_api_key="key" if configured else None,
    )
    monkeypatch.setattr(SettingsService, "resolve", lambda self: resolved)


def test_off_does_nothing(session: Session, _fake_radarr) -> None:
    assert scheduler.due_action(session, now=1000.0) == "off"
    assert _fake_radarr == []


def test_enabled_but_unscheduled_gets_armed(session: Session, _fake_radarr) -> None:
    row = SearchScheduleService(session).get()
    row.schedule = "daily"
    row.next_run_at = None
    session.commit()

    assert scheduler.due_action(session, now=1000.0) == "scheduled"
    assert SearchScheduleService(session).get().next_run_at is not None
    assert _fake_radarr == []


def test_not_yet_due_waits(session: Session, _fake_radarr) -> None:
    SearchScheduleService(session, clock=lambda: 1000.0).set_schedule("daily")
    # next_run_at is somewhere in (1000, 1000+DAY]; a moment right after arming
    # is definitely not due yet.
    assert scheduler.due_action(session, now=1000.5) == "waiting"
    assert _fake_radarr == []


def test_due_and_configured_triggers_and_advances(
    session: Session, monkeypatch, _fake_radarr
) -> None:
    _configure(monkeypatch, configured=True)
    svc = SearchScheduleService(session)
    svc.set_schedule("daily")
    row = svc.get()
    row.next_run_at = 500.0  # in the past → due
    session.commit()

    assert scheduler.due_action(session, now=1000.0) == "ok"
    assert _fake_radarr == [True]
    after = SearchScheduleService(session).get()
    assert after.last_result == "ok"
    assert after.last_run_at == 1000.0
    assert after.next_run_at > 1000.0  # rescheduled into the future


def test_due_but_unconfigured_skips(
    session: Session, monkeypatch, _fake_radarr
) -> None:
    _configure(monkeypatch, configured=False)
    svc = SearchScheduleService(session)
    svc.set_schedule("daily")
    row = svc.get()
    row.next_run_at = 500.0
    session.commit()

    assert scheduler.due_action(session, now=1000.0) == "skipped"
    assert _fake_radarr == []
    after = SearchScheduleService(session).get()
    assert after.last_result and after.last_result.startswith("skipped")
    assert after.next_run_at > 1000.0  # still advanced; won't retry every tick


def test_due_but_radarr_errors_records_error_and_advances(
    session: Session, monkeypatch
) -> None:
    _configure(monkeypatch, configured=True)

    def _boom(self):
        raise httpx.ConnectError(
            "down", request=httpx.Request("POST", "http://radarr/api/v3/command")
        )

    monkeypatch.setattr(RadarrService, "search_missing", _boom)
    svc = SearchScheduleService(session)
    svc.set_schedule("daily")
    row = svc.get()
    row.next_run_at = 500.0
    session.commit()

    result = scheduler.due_action(session, now=1000.0)
    assert result.startswith("error")
    after = SearchScheduleService(session).get()
    assert after.last_result.startswith("error")
    assert after.next_run_at > 1000.0
