import httpx
import pytest
from fastapi.testclient import TestClient

from app.clients.tmdb_client import TMDBClient
from app.main import app
from app.schemas.movie import Genre, Movie
from app.services.movie_service import MovieService
from app.web.routes import get_movie_service


def test_from_tmdb_maps_core_fields() -> None:
    movie = Movie.from_tmdb(
        {
            "id": 42,
            "title": "The Answer",
            "release_date": "2024-05-01",
            "vote_average": 7.456,
            "poster_path": "/abc.jpg",
            "overview": "A film.",
        }
    )
    assert movie.id == 42
    assert movie.title == "The Answer"
    assert movie.year == 2024
    assert movie.rating == 7.5  # rounded to one decimal
    assert movie.poster_url == "https://image.tmdb.org/t/p/w500/abc.jpg"
    assert movie.overview == "A film."


def test_from_tmdb_tolerates_missing_fields() -> None:
    movie = Movie.from_tmdb({"id": 1})
    assert movie.title == "Untitled"
    assert movie.year is None
    assert movie.rating is None
    assert movie.poster_url is None
    assert movie.overview == ""


def test_from_tmdb_zero_rating_is_none() -> None:
    movie = Movie.from_tmdb({"id": 1, "title": "X", "vote_average": 0})
    assert movie.rating is None


def test_from_tmdb_bad_release_date_is_none() -> None:
    movie = Movie.from_tmdb({"id": 1, "title": "X", "release_date": ""})
    assert movie.year is None


class _StubClient:
    """Returns the same payload for every list endpoint."""

    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def now_playing(self, page: int = 1) -> dict:
        return self._payload

    def upcoming(self, page: int = 1) -> dict:
        return self._payload

    def top_rated(self, page: int = 1) -> dict:
        return self._payload

    def discover(self, page: int = 1, params: dict | None = None) -> dict:
        return self._payload


def test_service_maps_results() -> None:
    payload = {"results": [{"id": 1, "title": "A"}, {"id": 2, "title": "B"}]}
    service = MovieService(_StubClient(payload))
    page = service.movies("in_theaters")
    assert [m.id for m in page.movies] == [1, 2]


def test_service_handles_empty_results() -> None:
    service = MovieService(_StubClient({}))
    assert service.movies("in_theaters").movies == []


def test_client_raises_on_http_error() -> None:
    # MockTransport lets us simulate a 401 without any real network call.
    transport = httpx.MockTransport(lambda request: httpx.Response(401, json={}))
    client = TMDBClient("bad-key", transport=transport)
    with pytest.raises(httpx.HTTPStatusError):
        client.now_playing()


def test_client_returns_payload_on_success() -> None:
    payload = {"results": [{"id": 1, "title": "Mock"}]}
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
    client = TMDBClient("good-key", transport=transport)
    assert client.now_playing() == payload


class _RaisingClient:
    def __init__(self, status_code: int = 401) -> None:
        self._status_code = status_code

    def now_playing(self, page: int = 1) -> dict:
        request = httpx.Request("GET", "https://api.themoviedb.org/3/movie/now_playing")
        response = httpx.Response(self._status_code, request=request)
        raise httpx.HTTPStatusError("error", request=request, response=response)


def test_movies_route_401_reports_api_key_problem() -> None:
    app.dependency_overrides[get_movie_service] = lambda: MovieService(_RaisingClient(401))
    try:
        with TestClient(app) as client:
            response = client.get("/movies?list=in_theaters")
        # The page must not 500; it points the user at the API key specifically.
        assert response.status_code == 200
        assert "API key" in response.text
    finally:
        app.dependency_overrides.clear()


def test_movies_route_other_error_shows_general_message() -> None:
    app.dependency_overrides[get_movie_service] = lambda: MovieService(_RaisingClient(503))
    try:
        with TestClient(app) as client:
            response = client.get("/movies?list=in_theaters")
        assert response.status_code == 200
        assert "Could not load movies" in response.text
    finally:
        app.dependency_overrides.clear()


def test_movies_route_renders_cards() -> None:
    payload = {"results": [{"id": 7, "title": "Render Me", "release_date": "2020-01-01"}]}
    app.dependency_overrides[get_movie_service] = lambda: MovieService(_StubClient(payload))
    try:
        with TestClient(app) as client:
            response = client.get("/movies?list=in_theaters")
        assert response.status_code == 200
        assert "Render Me" in response.text
        assert "2020" in response.text
    finally:
        app.dependency_overrides.clear()


def test_movies_route_unconfigured_shows_message() -> None:
    app.dependency_overrides[get_movie_service] = lambda: None
    try:
        with TestClient(app) as client:
            response = client.get("/movies")
        assert response.status_code == 200
        assert "not configured" in response.text
    finally:
        app.dependency_overrides.clear()


def test_genre_from_tmdb() -> None:
    genre = Genre.from_tmdb({"id": 53, "name": "Thriller"})
    assert genre.id == 53
    assert genre.name == "Thriller"


def test_genre_from_tmdb_missing_name() -> None:
    genre = Genre.from_tmdb({"id": 28})
    assert genre.id == 28
    assert genre.name == ""
