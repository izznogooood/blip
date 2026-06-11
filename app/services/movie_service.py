from datetime import date, timedelta

from app.clients.tmdb_client import TMDBClient
from app.schemas.movie import Movie, MoviePage

# The "Top Rated" list is not a TMDB chart — it is the highest-rated movies
# across all of Blip's *other* lists (see ADR-008). Its id is referenced by the
# aggregation logic so it can exclude itself from its own sources.
TOP_RATED_LIST_ID = "top_rated"

# v1 movie lists, in tab display order: (list id, human label).
# The id is used in URLs and dispatch; the label is shown in the tab bar.
MOVIE_LISTS: list[tuple[str, str]] = [
    ("in_theaters", "In Theaters"),
    ("upcoming_theatrical", "Upcoming Theatrical"),
    ("new_at_home", "New at Home"),
    ("upcoming_at_home", "Upcoming at Home"),
    (TOP_RATED_LIST_ID, "Top Rated"),
]

VALID_LIST_IDS = {list_id for list_id, _ in MOVIE_LISTS}

# TMDB release types: 4 = digital, 5 = physical. "At home" availability is
# approximated as a digital or physical release (see ADR-008).
_HOME_RELEASE_TYPES = "4|5"
# How far back a digital/physical release still counts as "new at home".
_NEW_AT_HOME_WINDOW_DAYS = 90
# How far ahead to look for announced home releases.
_UPCOMING_AT_HOME_WINDOW_DAYS = 180

# Short captions shown above a list's grid. Only lists with non-obvious
# behaviour need one; lists without an entry render no caption.
LIST_DESCRIPTIONS: dict[str, str] = {
    TOP_RATED_LIST_ID: (
        "The highest-rated movies across all of Blip's other lists — "
        "a curated snapshot, not a full TMDB chart."
    ),
}


class UnknownListError(ValueError):
    """Raised when a requested list id is not a known v1 list."""


class MovieService:
    """Business logic for fetching and shaping movie lists.

    Calls the TMDB client and maps raw responses into Blip's internal
    :class:`MoviePage` schema. Future milestones will merge Radarr status here.
    """

    def __init__(self, client: TMDBClient) -> None:
        self._client = client

    def movies(self, list_id: str, page: int = 1) -> MoviePage:
        """Fetch one page of the given list, mapped to a :class:`MoviePage`."""
        if list_id == TOP_RATED_LIST_ID:
            return self._top_rated()
        if list_id == "in_theaters":
            payload = self._client.now_playing(page=page)
        elif list_id == "upcoming_theatrical":
            payload = self._client.upcoming(page=page)
        elif list_id == "new_at_home":
            payload = self._client.discover(page=page, params=self._new_at_home_params())
        elif list_id == "upcoming_at_home":
            payload = self._client.discover(
                page=page, params=self._upcoming_at_home_params()
            )
        else:
            raise UnknownListError(list_id)
        return MoviePage.from_tmdb(payload)

    def _top_rated(self) -> MoviePage:
        """Assemble the highest-rated movies across all of Blip's other lists.

        Pulls page 1 of every other list in ``MOVIE_LISTS``, dedupes by movie id,
        and sorts by TMDB rating (highest first). Adding a new list to the
        registry automatically feeds into this view.

        Top Rated is a single curated page with no Load More: its pool is bounded
        by page 1 of each source list, so the whole set is shown at once.
        """
        source_ids = [
            list_id for list_id, _ in MOVIE_LISTS if list_id != TOP_RATED_LIST_ID
        ]

        unique: dict[int, Movie] = {}
        for source_id in source_ids:
            for movie in self.movies(source_id, page=1).movies:
                unique.setdefault(movie.id, movie)

        ranked = sorted(unique.values(), key=lambda m: m.rating or 0.0, reverse=True)
        return MoviePage(movies=ranked, page=1, total_pages=1)

    @staticmethod
    def _new_at_home_params() -> dict:
        today = date.today()
        start = today - timedelta(days=_NEW_AT_HOME_WINDOW_DAYS)
        return {
            "with_release_type": _HOME_RELEASE_TYPES,
            "release_date.gte": start.isoformat(),
            "release_date.lte": today.isoformat(),
            "sort_by": "primary_release_date.desc",
        }

    @staticmethod
    def _upcoming_at_home_params() -> dict:
        today = date.today()
        end = today + timedelta(days=_UPCOMING_AT_HOME_WINDOW_DAYS)
        return {
            "with_release_type": _HOME_RELEASE_TYPES,
            "release_date.gte": today.isoformat(),
            "release_date.lte": end.isoformat(),
            "sort_by": "primary_release_date.asc",
        }
