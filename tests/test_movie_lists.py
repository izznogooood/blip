import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.movie import MoviePage
from app.services.movie_service import (
    MOVIE_LISTS,
    MovieService,
    UnknownListError,
)
from app.web.routes import get_movie_service


class _RecordingClient:
    """Records which endpoint/params were called and returns a canned payload."""

    def __init__(self, payload: dict | None = None) -> None:
        self.payload = payload or {"results": [], "page": 1, "total_pages": 1}
        self.calls: list[tuple[str, dict]] = []

    def now_playing(self, page: int = 1) -> dict:
        self.calls.append(("now_playing", {"page": page}))
        return self.payload

    def upcoming(self, page: int = 1) -> dict:
        self.calls.append(("upcoming", {"page": page}))
        return self.payload

    def discover(self, page: int = 1, params: dict | None = None) -> dict:
        self.calls.append(("discover", {"page": page, **(params or {})}))
        return self.payload

    def genres(self) -> dict:
        return {"genres": [{"id": 28, "name": "Action"}, {"id": 53, "name": "Thriller"}]}


# "top_rated" is excluded — it is an aggregate of the other lists, not a single
# TMDB endpoint (see ADR-008 and test_top_rated_* below).
@pytest.mark.parametrize(
    "list_id,expected_endpoint",
    [
        ("in_theaters", "now_playing"),
        ("upcoming_theatrical", "upcoming"),
        ("new_at_home", "discover"),
        ("upcoming_at_home", "discover"),
    ],
)
def test_each_list_dispatches_to_expected_endpoint(list_id, expected_endpoint) -> None:
    client = _RecordingClient()
    MovieService(client).movies(list_id, page=2)
    assert client.calls[0][0] == expected_endpoint
    assert client.calls[0][1]["page"] == 2


def test_unknown_list_raises() -> None:
    with pytest.raises(UnknownListError):
        MovieService(_RecordingClient()).movies("nope")


class _MultiListClient:
    """Returns a distinct movie per endpoint so aggregation can be observed."""

    def now_playing(self, page: int = 1) -> dict:
        return {"results": [{"id": 1, "title": "A", "vote_average": 6.0}]}

    def upcoming(self, page: int = 1) -> dict:
        return {"results": [{"id": 2, "title": "B", "vote_average": 9.0}]}

    def discover(self, page: int = 1, params: dict | None = None) -> dict:
        # id 1 also appears in now_playing — must be deduped, not double-counted.
        return {
            "results": [
                {"id": 1, "title": "A", "vote_average": 6.0},
                {"id": 3, "title": "C", "vote_average": 7.5},
            ]
        }


def test_top_rated_aggregates_dedupes_and_sorts_other_lists() -> None:
    page = MovieService(_MultiListClient()).movies("top_rated")
    # Highest rating first, id 1 appears once despite being in two source lists.
    assert [m.id for m in page.movies] == [2, 3, 1]


def test_top_rated_is_a_single_page_with_no_load_more() -> None:
    # Even with many movies, Top Rated shows the whole curated pool at once.
    class _ManyClient:
        def now_playing(self, page: int = 1) -> dict:
            return {
                "results": [
                    {"id": i, "title": str(i), "vote_average": float(i)}
                    for i in range(25)
                ]
            }

        def upcoming(self, page: int = 1) -> dict:
            return {"results": []}

        def discover(self, page: int = 1, params: dict | None = None) -> dict:
            return {"results": []}

    page = MovieService(_ManyClient()).movies("top_rated")
    assert len(page.movies) == 25
    assert page.has_more is False


def test_top_rated_route_shows_caption_and_no_load_more() -> None:
    app.dependency_overrides[get_movie_service] = lambda: MovieService(
        _MultiListClient()
    )
    try:
        with TestClient(app) as client:
            response = client.get("/movies?list=top_rated")
        assert "highest-rated movies across all of Blip" in response.text
        assert "Load More" not in response.text
    finally:
        app.dependency_overrides.clear()


def test_new_at_home_uses_home_release_types_and_descending_sort() -> None:
    client = _RecordingClient()
    MovieService(client).movies("new_at_home")
    params = client.calls[0][1]
    assert params["with_release_type"] == "4|5"
    assert params["sort_by"] == "primary_release_date.desc"
    # Newest-first window: lower bound is before the upper bound.
    assert params["release_date.gte"] < params["release_date.lte"]


def test_upcoming_at_home_sorts_ascending_into_the_future() -> None:
    client = _RecordingClient()
    MovieService(client).movies("upcoming_at_home")
    params = client.calls[0][1]
    assert params["with_release_type"] == "4|5"
    assert params["sort_by"] == "primary_release_date.asc"
    assert params["release_date.gte"] < params["release_date.lte"]


def test_movie_page_has_more_reflects_pagination() -> None:
    page = MoviePage.from_tmdb({"results": [], "page": 1, "total_pages": 3})
    assert page.has_more is True
    last = MoviePage.from_tmdb({"results": [], "page": 3, "total_pages": 3})
    assert last.has_more is False


def test_index_renders_all_list_tabs() -> None:
    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200
    for _, label in MOVIE_LISTS:
        assert label in response.text


def test_page_one_returns_full_grid_with_load_more() -> None:
    payload = {
        "results": [{"id": 1, "title": "First"}],
        "page": 1,
        "total_pages": 2,
    }
    app.dependency_overrides[get_movie_service] = lambda: MovieService(
        _RecordingClient(payload)
    )
    try:
        with TestClient(app) as client:
            response = client.get("/movies?list=in_theaters&page=1")
        assert 'id="movie-cards"' in response.text  # full grid wrapper present
        assert 'id="load-more"' in response.text
        assert "page=2" in response.text  # Load More points at the next page
    finally:
        app.dependency_overrides.clear()


def test_load_more_page_returns_append_fragment_without_grid_wrapper() -> None:
    payload = {
        "results": [{"id": 2, "title": "Second"}],
        "page": 2,
        "total_pages": 2,
    }
    app.dependency_overrides[get_movie_service] = lambda: MovieService(
        _RecordingClient(payload)
    )
    try:
        with TestClient(app) as client:
            response = client.get("/movies?list=in_theaters&page=2")
        assert "Second" in response.text
        # No new grid wrapper on append; the cards go into the existing grid.
        assert 'id="movie-cards"' not in response.text
        # Button swaps itself out-of-band; on the last page it is now empty.
        assert "hx-swap-oob" in response.text
        assert "Load More" not in response.text
    finally:
        app.dependency_overrides.clear()


def test_unknown_list_route_shows_error() -> None:
    app.dependency_overrides[get_movie_service] = lambda: MovieService(
        _RecordingClient()
    )
    try:
        with TestClient(app) as client:
            response = client.get("/movies?list=bogus")
        assert response.status_code == 200
        assert "Unknown list" in response.text
    finally:
        app.dependency_overrides.clear()


def test_genre_movies_dispatches_to_discover() -> None:
    client = _RecordingClient()
    MovieService(client).genre_movies(53, page=1)
    assert client.calls[0][0] == "discover"
    params = client.calls[0][1]
    assert params["with_genres"] == "53"
    assert params["sort_by"] == "primary_release_date.desc"


def test_genre_movies_uses_180_day_window() -> None:
    client = _RecordingClient()
    MovieService(client).genre_movies(28, page=1)
    params = client.calls[0][1]
    assert "release_date.gte" in params
    assert "release_date.lte" in params


def test_genre_movies_sorts_by_date_by_default() -> None:
    client = _RecordingClient()
    MovieService(client).genre_movies(28, page=1)
    assert client.calls[0][1]["sort_by"] == "primary_release_date.desc"


def test_genre_movies_sorts_by_rating_when_requested() -> None:
    client = _RecordingClient()
    MovieService(client).genre_movies(28, page=1, sort_by_rating=True)
    assert client.calls[0][1]["sort_by"] == "vote_average.desc"


def test_genre_route_shows_caption() -> None:
    recording = _RecordingClient()
    app.dependency_overrides[get_movie_service] = lambda: MovieService(recording)
    try:
        with TestClient(app) as tc:
            response = tc.get("/movies?genre_id=53")
        assert response.status_code == 200
        assert "Thriller" in response.text
        assert "180 days" in response.text
    finally:
        app.dependency_overrides.clear()


def test_genre_route_load_more_includes_genre_id() -> None:
    payload = {
        "results": [{"id": 1, "title": "Genre Movie"}],
        "page": 1,
        "total_pages": 2,
    }
    app.dependency_overrides[get_movie_service] = lambda: MovieService(
        _RecordingClient(payload)
    )
    try:
        with TestClient(app) as tc:
            response = tc.get("/movies?genre_id=53&page=1")
        assert "Load More" in response.text
        assert "genre_id=53" in response.text  # Load More preserves genre
    finally:
        app.dependency_overrides.clear()
