import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.movie import Movie
from app.schemas.radarr import (
    QualityProfile,
    RadarrStatus,
    RootFolder,
    status_from_radarr,
)
from app.services.radarr_service import RadarrService
from app.web.routes import get_radarr_service


class _StubClient:
    """Radarr client stub returning canned library/profile/folder payloads."""

    def __init__(self, movies: list[dict] | None = None) -> None:
        self._movies = movies or []

    def movies(self) -> list[dict]:
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


# --- route integration -------------------------------------------------------


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
