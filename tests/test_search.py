import httpx
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.clients.tmdb_client import TMDBClient
from app.core.database import Base
from app.main import app
from app.models.cache import CachedResponse  # noqa: F401  registers the table
from app.services.cache_service import CacheService
from app.services.movie_service import MovieService
from app.web.routes import get_movie_service


class _SearchRecordingClient:
    """Records search calls and returns a canned payload."""

    def __init__(self, payload: dict | None = None) -> None:
        self.payload = payload or {"results": [], "page": 1, "total_pages": 1}
        self.calls: list[tuple[str, int]] = []

    def search(self, query: str, page: int = 1) -> dict:
        self.calls.append((query, page))
        return self.payload

    def genres(self) -> dict:
        return {"genres": []}


def test_client_search_hits_search_movie_endpoint() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["query"] = request.url.params.get("query")
        captured["page"] = request.url.params.get("page")
        return httpx.Response(200, json={"results": []})

    client = TMDBClient("key", transport=httpx.MockTransport(handler))
    client.search("dune", page=2)
    assert captured["path"].endswith("/search/movie")
    assert captured["query"] == "dune"
    assert int(captured["page"]) == 2


def test_service_search_maps_results() -> None:
    payload = {"results": [{"id": 1, "title": "Dune"}], "page": 1, "total_pages": 3}
    page = MovieService(_SearchRecordingClient(payload)).search("dune")
    assert [m.id for m in page.movies] == [1]
    assert page.has_more is True


def test_service_search_caches_by_query_and_page() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        client = _SearchRecordingClient({"results": [{"id": 1, "title": "Dune"}]})
        service = MovieService(client, cache=CacheService(session))
        service.search("Dune")
        service.search("dune")  # case-insensitive cache key → no second call
        assert len(client.calls) == 1


def test_search_route_renders_results_and_caption() -> None:
    payload = {"results": [{"id": 7, "title": "Render Me"}], "page": 1, "total_pages": 2}
    app.dependency_overrides[get_movie_service] = lambda: MovieService(
        _SearchRecordingClient(payload)
    )
    try:
        with TestClient(app) as client:
            response = client.get("/movies?query=render")
        assert response.status_code == 200
        assert "Render Me" in response.text
        assert "Showing results for" in response.text
        # Load More preserves the query.
        assert "query=render" in response.text
    finally:
        app.dependency_overrides.clear()


def test_search_route_takes_precedence_over_list() -> None:
    client = _SearchRecordingClient()
    app.dependency_overrides[get_movie_service] = lambda: MovieService(client)
    try:
        with TestClient(app) as tc:
            tc.get("/movies?query=dune&list=in_theaters")
        assert client.calls == [("dune", 1)]
    finally:
        app.dependency_overrides.clear()


def test_blank_query_falls_back_to_list() -> None:
    payload = {"results": [{"id": 1, "title": "In Theaters Movie"}]}

    class _ListClient(_SearchRecordingClient):
        def now_playing(self, page: int = 1) -> dict:
            return payload

    app.dependency_overrides[get_movie_service] = lambda: MovieService(_ListClient())
    try:
        with TestClient(app) as tc:
            response = tc.get("/movies?query=%20%20")  # whitespace only
        assert "In Theaters Movie" in response.text
    finally:
        app.dependency_overrides.clear()


def test_search_route_empty_results_shows_no_movies() -> None:
    app.dependency_overrides[get_movie_service] = lambda: MovieService(
        _SearchRecordingClient({"results": [], "page": 1, "total_pages": 1})
    )
    try:
        with TestClient(app) as client:
            response = client.get("/movies?query=zzznope")
        assert "No movies to show." in response.text
    finally:
        app.dependency_overrides.clear()


def test_search_pagination_preserves_query() -> None:
    """Page 2+ returns the append fragment with Load More pointing to the
    next page and preserving the query parameter."""
    payload = {"results": [{"id": 8, "title": "Page Two"}], "page": 2, "total_pages": 5}
    app.dependency_overrides[get_movie_service] = lambda: MovieService(
        _SearchRecordingClient(payload)
    )
    try:
        with TestClient(app) as client:
            response = client.get("/movies?query=dune&page=2")
        assert response.status_code == 200
        assert "Page Two" in response.text
        # Should NOT include the full-grid Refresh button (only on page 1).
        assert "Refresh Cache" not in response.text
        # Load More should point to page 3 and preserve the query.
        assert 'query=dune' in response.text
        assert 'page=3' in response.text
    finally:
        app.dependency_overrides.clear()


def test_search_force_refresh_bypasses_cache() -> None:
    """Force-refreshing a search skips the cache and calls the client again."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        client = _SearchRecordingClient({"results": [{"id": 1, "title": "Dune"}]})
        service = MovieService(client, cache=CacheService(session))
        # First call populates the cache.
        service.search("Dune")
        # Second call with force_refresh bypasses cache → calls client again.
        service.search("Dune", force_refresh=True)
        assert len(client.calls) == 2


def test_index_renders_search_box() -> None:
    app.dependency_overrides[get_movie_service] = lambda: MovieService(
        _SearchRecordingClient()
    )
    try:
        with TestClient(app) as client:
            response = client.get("/")
        assert 'id="search-input"' in response.text
    finally:
        app.dependency_overrides.clear()
