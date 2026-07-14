import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base
from app.models.search_schedule import SearchSchedule  # noqa: F401  registers table
from app.services.search_schedule_service import (
    SearchScheduleService,
    compute_next_run,
)

DAY = 86_400
WEEK = 604_800


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as s:
        yield s


def _service(session: Session, now: float = 1000.0) -> SearchScheduleService:
    return SearchScheduleService(session, clock=lambda: now)


def test_compute_next_run_first_lands_within_one_period() -> None:
    for _ in range(200):
        nxt = compute_next_run(1000.0, DAY, first=True)
        assert 1000.0 <= nxt <= 1000.0 + DAY


def test_compute_next_run_subsequent_jitters_around_a_period() -> None:
    for _ in range(200):
        nxt = compute_next_run(1000.0, WEEK, first=False)
        assert 1000.0 + 0.5 * WEEK <= nxt <= 1000.0 + 1.5 * WEEK


def test_get_creates_default_off_row(session: Session) -> None:
    row = _service(session).get()
    assert row.schedule == "off"
    assert row.next_run_at is None


def test_set_schedule_arms_next_run(session: Session) -> None:
    row = _service(session).set_schedule("daily")
    assert row.schedule == "daily"
    assert row.next_run_at is not None
    assert 1000.0 < row.next_run_at <= 1000.0 + DAY


def test_set_schedule_same_value_keeps_next_run(session: Session) -> None:
    svc = _service(session)
    first = svc.set_schedule("daily").next_run_at
    again = svc.set_schedule("daily").next_run_at
    assert again == first


def test_set_schedule_off_clears_next_run(session: Session) -> None:
    svc = _service(session)
    svc.set_schedule("weekly")
    row = svc.set_schedule("off")
    assert row.schedule == "off"
    assert row.next_run_at is None


def test_set_schedule_invalid_value_falls_back_to_off(session: Session) -> None:
    row = _service(session).set_schedule("hourly")
    assert row.schedule == "off"


def test_record_run_updates_last_and_next(session: Session) -> None:
    svc = _service(session)
    svc.set_schedule("daily")
    svc.record_run(run_at=2000.0, next_run_at=99_999.0, result="ok")
    row = svc.get()
    assert row.last_run_at == 2000.0
    assert row.last_result == "ok"
    assert row.next_run_at == 99_999.0


def test_record_manual_run_leaves_next_run_untouched(session: Session) -> None:
    svc = _service(session)
    scheduled = svc.set_schedule("daily").next_run_at
    svc.record_manual_run(run_at=3000.0, result="ok")
    row = svc.get()
    assert row.last_run_at == 3000.0
    assert row.last_result == "ok"
    assert row.next_run_at == scheduled  # schedule not disturbed
