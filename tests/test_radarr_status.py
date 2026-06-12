import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base
from app.main import app
from app.schemas.movie import Movie
from app.schemas.radarr import (
    QualityProfile,
    RadarrStatus,
    RootFolder,
    status_from_radarr,
)
from app.services.cache_service import CacheService
from app.services.radarr_service import RadarrService
from app.web.routes import get_radarr_service


class _Clock:
    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as s:
        yield s


class _StubClient:
    """Radarr client stub returning canned library/profile/folder payloads."""

    def __init__(self, movies: list[dict] | None = None) -> None:
        self._movies = movies or []
        self.movies_calls = 0

    def movies(self) -> list[dict]:
        self.movies_calls += 1
        return self._movies

    def quality_profiles(self) -> list[dict]:
        return [{"id": 1, "name": "HD-1080p"}, {"id": 2}]

    def root_folders(self) -> list[dict]:
        return [{"id": 1, "path": "/movies"}]


# --- status mapping ----------------------------------------------------------


@pytest.mark.parametrize(
    "payload,expected",
    [
        ({"hasFile": True, "monitored": True}, RadarrStatus.DOWNLOADED),
        ({"hasFile": True, "monitored": False}, RadarrStatus.DOWNLOADED),
        ({"hasFile": False, "monitored": True}, RadarrStatus.MISSING),
        ({"hasFile": False, "monitored": False}, RadarrStatus.UNMONITORED),
        ({}, RadarrStatus.UNKNOWN),
    ],
)
def test_status_mapping(payload, expected) -> None:
    assert status_from_radarr(payload) == expected


def test_statuses_by_tmdb_id_skips_entries_without_tmdb_id_and_dedupes() -> None:
    client = _StubClient(
        [
            {"tmdbId": 10, "hasFile": True, "monitored": True},
            {"tmdbId": 20, "hasFile": False, "monitored": False},
            {"hasFile": True},  # no tmdbId → skipped
            {"tmdbId": 10, "hasFile": False, "monitored": True},  # dup → first wins
        ]
    )
    statuses = RadarrService(client).statuses_by_tmdb_id()
    assert statuses == {10: RadarrStatus.DOWNLOADED, 20: RadarrStatus.UNMONITORED}


def test_annotate_sets_status_only_for_library_movies() -> None:
    client = _StubClient([{"tmdbId": 1, "hasFile": True, "monitored": True}])
    movies = [Movie(id=1, title="In"), Movie(id=2, title="Out")]
    RadarrService(client).annotate(movies)
    assert movies[0].radarr_status == RadarrStatus.DOWNLOADED
    assert movies[0].in_radarr is True
    assert movies[1].radarr_status is None
    assert movies[1].in_radarr is False


def test_quality_profiles_and_root_folders_map() -> None:
    service = RadarrService(_StubClient())
    profiles = service.quality_profiles()
    assert profiles == [
        QualityProfile(id=1, name="HD-1080p"),
        QualityProfile(id=2, name="Profile 2"),  # name falls back to id
    ]
    assert service.root_folders() == [RootFolder(id=1, path="/movies")]


def test_statuses_cache_is_used_within_ttl(session: Session) -> None:
    client = _StubClient([{"tmdbId": 1, "hasFile": True, "monitored": True}])
    service = RadarrService(client, cache=CacheService(session))
    service.statuses_by_tmdb_id()
    service.statuses_by_tmdb_id()
    assert client.movies_calls == 1


def test_statuses_force_refresh_bypasses_cache(session: Session) -> None:
    client = _StubClient([{"tmdbId": 1, "hasFile": True, "monitored": True}])
    service = RadarrService(client, cache=CacheService(session))
    service.statuses_by_tmdb_id()
    service.statuses_by_tmdb_id(force_refresh=True)
    assert client.movies_calls == 2


def test_statuses_cache_expires(session: Session) -> None:
    clock = _Clock()
    client = _StubClient([{"tmdbId": 1, "hasFile": True, "monitored": True}])
    service = RadarrService(client, cache=CacheService(session, clock=clock))
    service.statuses_by_tmdb_id()
    clock.now += 601
    service.statuses_by_tmdb_id()
    assert client.movies_calls == 2


# --- route integration -------------------------------------------------------


def test_movies_route_forces_radarr_refresh_on_page_one_and_refresh_flag() -> None:
    from app.services.movie_service import MovieService
    from app.web.routes import get_movie_service

    class _MovieClient:
        def now_playing(self, page: int = 1) -> dict:
            return {
                "results": [{"id": 1, "title": "Known", "poster_path": "/p.jpg"}],
                "page": page,
                "total_pages": 2,
            }

    class _RadarrRecorder:
        def __init__(self) -> None:
            self.force_refresh_calls: list[bool] = []

        def annotate(self, movies, *, force_refresh: bool = False) -> None:
            self.force_refresh_calls.append(force_refresh)

        def quality_profiles(self) -> list[dict]:
            return []

    recorder = _RadarrRecorder()
    app.dependency_overrides[get_movie_service] = lambda: MovieService(_MovieClient())
    app.dependency_overrides[get_radarr_service] = lambda: recorder
    try:
        with TestClient(app) as client:
            client.get("/movies?list=in_theaters&page=1")
            client.get("/movies?list=in_theaters&page=2")
            client.get("/movies?list=in_theaters&page=2&refresh=true")
        assert recorder.force_refresh_calls == [True, False, True]
    finally:
        app.dependency_overrides.clear()


def test_movies_route_renders_status_badge_and_grays_existing() -> None:
    from app.services.movie_service import MovieService
    from app.web.routes import get_movie_service

    class _MovieClient:
        def now_playing(self, page: int = 1) -> dict:
            return {
                "results": [
                    {"id": 1, "title": "Known", "poster_path": "/p.jpg"},
                    {"id": 2, "title": "Unknown"},
                ],
                "page": 1,
                "total_pages": 1,
            }

    app.dependency_overrides[get_movie_service] = lambda: MovieService(_MovieClient())
    app.dependency_overrides[get_radarr_service] = lambda: RadarrService(
        _StubClient([{"tmdbId": 1, "hasFile": True, "monitored": True}])
    )
    try:
        with TestClient(app) as client:
            response = client.get("/movies?list=in_theaters")
        assert "Downloaded" in response.text  # badge for the in-library movie
        assert "Already in Radarr" in response.text
        assert "grayscale" in response.text  # existing poster desaturated
    finally:
        app.dependency_overrides.clear()


def test_movies_route_renders_when_radarr_unconfigured() -> None:
    from app.services.movie_service import MovieService
    from app.web.routes import get_movie_service

    class _MovieClient:
        def now_playing(self, page: int = 1) -> dict:
            return {"results": [{"id": 1, "title": "X"}], "page": 1, "total_pages": 1}

    app.dependency_overrides[get_movie_service] = lambda: MovieService(_MovieClient())
    app.dependency_overrides[get_radarr_service] = lambda: None
    try:
        with TestClient(app) as client:
            response = client.get("/movies?list=in_theaters")
        assert response.status_code == 200
        assert "X" in response.text
        assert "Already in Radarr" not in response.text
    finally:
        app.dependency_overrides.clear()
