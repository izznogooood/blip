from fastapi.testclient import TestClient

from app.main import app
from app.schemas.movie import MovieDetail, _trailer_key
from app.services.movie_service import MovieService
from app.web.routes import get_movie_service

# --- trailer extraction -------------------------------------------------------


def test_trailer_prefers_official_youtube_trailer() -> None:
    videos = {
        "results": [
            {"site": "YouTube", "type": "Teaser", "key": "teaser", "official": True},
            {"site": "YouTube", "type": "Trailer", "key": "unofficial", "official": False},
            {"site": "YouTube", "type": "Trailer", "key": "official", "official": True},
        ]
    }
    assert _trailer_key(videos) == "official"


def test_trailer_falls_back_to_any_trailer_then_teaser() -> None:
    assert _trailer_key({"results": [{"site": "YouTube", "type": "Trailer", "key": "t"}]}) == "t"
    assert _trailer_key({"results": [{"site": "YouTube", "type": "Teaser", "key": "z"}]}) == "z"


def test_trailer_ignores_non_youtube_and_missing() -> None:
    assert _trailer_key({"results": [{"site": "Vimeo", "type": "Trailer", "key": "v"}]}) is None
    assert _trailer_key(None) is None
    assert _trailer_key({}) is None


# --- detail mapping -----------------------------------------------------------


def test_detail_from_tmdb_maps_fields_and_builds_trailer_url() -> None:
    detail = MovieDetail.from_tmdb(
        {
            "id": 5,
            "title": "Deep Film",
            "release_date": "2023-03-10",
            "vote_average": 8.21,
            "poster_path": "/p.jpg",
            "overview": "A synopsis.",
            "videos": {"results": [{"site": "YouTube", "type": "Trailer", "key": "abc"}]},
        }
    )
    assert detail.id == 5
    assert detail.title == "Deep Film"
    assert detail.year == 2023
    assert detail.rating == 8.2
    assert detail.poster_url == "https://image.tmdb.org/t/p/w500/p.jpg"
    assert detail.release_date == "2023-03-10"
    assert detail.trailer_url == "https://www.youtube.com/watch?v=abc"


def test_detail_without_trailer_has_none_url() -> None:
    detail = MovieDetail.from_tmdb({"id": 1, "title": "X"})
    assert detail.trailer_url is None
    assert detail.overview == ""


# --- route --------------------------------------------------------------------


class _DetailClient:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def movie_details(self, movie_id: int) -> dict:
        return {"id": movie_id, **self._payload}


def test_modal_route_renders_overview_and_trailer() -> None:
    payload = {
        "title": "Modal Movie",
        "overview": "An overview here.",
        "videos": {"results": [{"site": "YouTube", "type": "Trailer", "key": "yt9"}]},
    }
    app.dependency_overrides[get_movie_service] = lambda: MovieService(_DetailClient(payload))
    try:
        with TestClient(app) as http:
            response = http.get("/movies/7/modal")
        assert response.status_code == 200
        assert "Modal Movie" in response.text
        assert "An overview here." in response.text
        assert "https://www.youtube.com/watch?v=yt9" in response.text
        assert "Trailer" in response.text
    finally:
        app.dependency_overrides.clear()


def test_modal_route_renders_add_controls() -> None:
    # No Radarr override → movie not in library → modal offers Add controls.
    app.dependency_overrides[get_movie_service] = lambda: MovieService(
        _DetailClient({"title": "Addable Film"})
    )
    try:
        with TestClient(app) as http:
            response = http.get("/movies/7/modal")
        assert response.status_code == 200
        assert 'id="movie-actions-modal-7"' in response.text
        assert "Add + Search" in response.text
        # The modal form tells the route the request came from the modal.
        assert 'name="source" value="modal"' in response.text
    finally:
        app.dependency_overrides.clear()


def test_modal_route_hides_trailer_when_absent() -> None:
    app.dependency_overrides[get_movie_service] = lambda: MovieService(
        _DetailClient({"title": "No Trailer Film", "overview": "x"})
    )
    try:
        with TestClient(app) as http:
            response = http.get("/movies/7/modal")
        assert response.status_code == 200
        assert "youtube.com" not in response.text
    finally:
        app.dependency_overrides.clear()


def test_modal_route_unconfigured_shows_message() -> None:
    app.dependency_overrides[get_movie_service] = lambda: None
    try:
        with TestClient(app) as http:
            response = http.get("/movies/7/modal")
        assert response.status_code == 200
        assert "not configured" in response.text
    finally:
        app.dependency_overrides.clear()
