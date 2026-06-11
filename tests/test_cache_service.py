import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base
from app.models.cache import CachedResponse  # noqa: F401  registers the table
from app.services.cache_service import LIST_CACHE_TTL, CacheService
from app.services.movie_service import MovieService


@pytest.fixture
def session() -> Session:
    """An isolated in-memory SQLite session with the cache table created."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as s:
        yield s


class _Clock:
    """A controllable monotonic clock for deterministic expiry tests."""

    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now


class _CountingClient:
    """TMDB client stub that counts how many times each endpoint is hit."""

    def __init__(self) -> None:
        self.calls = 0

    def now_playing(self, page: int = 1) -> dict:
        self.calls += 1
        return {"results": [{"id": self.calls, "title": "M"}], "page": page,
                "total_pages": 1}

    def upcoming(self, page: int = 1) -> dict:
        self.calls += 1
        return {"results": [], "page": page, "total_pages": 1}

    def discover(self, page: int = 1, params: dict | None = None) -> dict:
        self.calls += 1
        return {"results": [], "page": page, "total_pages": 1}


# --- CacheService unit tests -------------------------------------------------


def test_get_returns_none_on_miss(session: Session) -> None:
    cache = CacheService(session)
    assert cache.get("absent") is None


def test_set_then_get_round_trips_payload(session: Session) -> None:
    cache = CacheService(session)
    payload = {"results": [{"id": 1}], "page": 1}
    cache.set("k", payload, LIST_CACHE_TTL)
    assert cache.get("k") == payload


def test_expired_entry_is_a_miss_and_is_pruned(session: Session) -> None:
    clock = _Clock()
    cache = CacheService(session, clock=clock)
    cache.set("k", {"v": 1}, ttl=60)
    clock.now += 61  # advance past the TTL
    assert cache.get("k") is None
    assert session.get(CachedResponse, "k") is None  # pruned on read


def test_set_overwrites_existing_key(session: Session) -> None:
    cache = CacheService(session)
    cache.set("k", {"v": 1}, LIST_CACHE_TTL)
    cache.set("k", {"v": 2}, LIST_CACHE_TTL)
    assert cache.get("k") == {"v": 2}


# --- MovieService caching integration ---------------------------------------


def test_repeated_loads_use_cache(session: Session) -> None:
    client = _CountingClient()
    service = MovieService(client, cache=CacheService(session))
    service.movies("in_theaters", page=1)
    service.movies("in_theaters", page=1)
    assert client.calls == 1  # second load served from cache


def test_different_pages_are_cached_separately(session: Session) -> None:
    client = _CountingClient()
    service = MovieService(client, cache=CacheService(session))
    service.movies("in_theaters", page=1)
    service.movies("in_theaters", page=2)
    assert client.calls == 2


def test_force_refresh_bypasses_and_updates_cache(session: Session) -> None:
    client = _CountingClient()
    service = MovieService(client, cache=CacheService(session))
    service.movies("in_theaters", page=1)
    service.movies("in_theaters", page=1, force_refresh=True)
    assert client.calls == 2  # refresh re-fetched despite a warm cache
    # The refreshed payload is now what a subsequent cached read returns.
    service.movies("in_theaters", page=1)
    assert client.calls == 2


def test_expired_cache_triggers_refetch(session: Session) -> None:
    clock = _Clock()
    client = _CountingClient()
    service = MovieService(client, cache=CacheService(session, clock=clock))
    service.movies("in_theaters", page=1)
    clock.now += LIST_CACHE_TTL + 1
    service.movies("in_theaters", page=1)
    assert client.calls == 2


def test_service_works_without_a_cache(session: Session) -> None:
    client = _CountingClient()
    service = MovieService(client)  # no cache configured
    service.movies("in_theaters", page=1)
    service.movies("in_theaters", page=1)
    assert client.calls == 2  # every load hits the client
