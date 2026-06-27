from collections.abc import Callable
from datetime import date, timedelta

from app.clients.tmdb_client import TMDBClient
from app.schemas.movie import Genre, Movie, MovieDetail, MoviePage
from app.services.cache_service import (
    DETAILS_CACHE_TTL,
    LIST_CACHE_TTL,
    CacheService,
)

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
# How far back to look when browsing movies by genre.
_GENRE_WINDOW_DAYS = 180
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

    def __init__(self, client: TMDBClient, *, cache: CacheService | None = None) -> None:
        self._client = client
        self._cache = cache

    def movies(
        self, list_id: str, page: int = 1, *, force_refresh: bool = False
    ) -> MoviePage:
        """Fetch one page of the given list, mapped to a :class:`MoviePage`.

        Responses are served from the cache when available; ``force_refresh``
        bypasses the cache and refreshes the stored payload (used by the manual
        per-list refresh action).
        """
        if list_id == TOP_RATED_LIST_ID:
            return self._top_rated(force_refresh=force_refresh)
        payload = self._fetch_list(list_id, page, force_refresh=force_refresh)
        return MoviePage.from_tmdb(payload)

    def genres(self, *, force_refresh: bool = False) -> list[Genre]:
        """Return the full list of TMDB movie genres.

        Cached for 24 hours since the genre taxonomy rarely changes.
        """
        payload = self._cached(
            "tmdb:genres",
            lambda: self._client.genres(),
            force_refresh,
            ttl=DETAILS_CACHE_TTL,
        )
        return [Genre.from_tmdb(g) for g in (payload.get("genres") or [])]

    def genre_map(self, *, force_refresh: bool = False) -> dict[int, str]:
        """Return a lookup dict mapping genre ID → genre name.

        Reuses the cached genre list so no additional API calls are made.
        """
        return {g.id: g.name for g in self.genres(force_refresh=force_refresh)}

    def genre_movies(
        self, genre_id: int, page: int = 1, *, sort_by_rating: bool = False, force_refresh: bool = False
    ) -> MoviePage:
        """Fetch one page of movies for ``genre_id`` released in the last 180 days."""
        cache_key = f"tmdb:genre:{genre_id}:{page}:{'rating' if sort_by_rating else 'date'}"
        payload = self._cached(
            cache_key,
            lambda: self._client.discover(
                page=page, params=self._genre_params(genre_id, sort_by_rating=sort_by_rating)
            ),
            force_refresh,
        )
        return MoviePage.from_tmdb(payload)

    def details(self, movie_id: int, *, force_refresh: bool = False) -> MovieDetail:
        """Fetch a movie's details (overview, trailer) for the synopsis modal.

        Cached for 24 hours (PRD §13) under a ``tmdb:detail:{id}`` key.
        """
        payload = self._cached(
            f"tmdb:detail:{movie_id}",
            lambda: self._client.movie_details(movie_id),
            force_refresh,
            ttl=DETAILS_CACHE_TTL,
        )
        return MovieDetail.from_tmdb(payload)

    def _fetch_list(self, list_id: str, page: int, *, force_refresh: bool) -> dict:
        """Return the raw TMDB payload for a (non-aggregate) list, via the cache."""
        if list_id == "in_theaters":
            fetch: Callable[[], dict] = lambda: self._client.now_playing(page=page)
        elif list_id == "upcoming_theatrical":
            fetch = lambda: self._client.upcoming(page=page)
        elif list_id == "new_at_home":
            fetch = lambda: self._client.discover(
                page=page, params=self._new_at_home_params()
            )
        elif list_id == "upcoming_at_home":
            fetch = lambda: self._client.discover(
                page=page, params=self._upcoming_at_home_params()
            )
        else:
            raise UnknownListError(list_id)
        return self._cached(f"tmdb:list:{list_id}:{page}", fetch, force_refresh)

    def _cached(
        self,
        key: str,
        fetch: Callable[[], dict],
        force_refresh: bool,
        *,
        ttl: int = LIST_CACHE_TTL,
    ) -> dict:
        """Return ``fetch()``'s result, reading/writing the cache if present."""
        if self._cache is not None and not force_refresh:
            cached = self._cache.get(key)
            if cached is not None:
                return cached
        payload = fetch()
        if self._cache is not None:
            self._cache.set(key, payload, ttl)
        return payload

    def _top_rated(self, *, force_refresh: bool = False) -> MoviePage:
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
            page = self.movies(source_id, page=1, force_refresh=force_refresh)
            for movie in page.movies:
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
    def _genre_params(genre_id: int, *, sort_by_rating: bool = False) -> dict:
        today = date.today()
        start = today - timedelta(days=_GENRE_WINDOW_DAYS)
        return {
            "with_genres": str(genre_id),
            "release_date.gte": start.isoformat(),
            "release_date.lte": today.isoformat(),
            "sort_by": "vote_average.desc" if sort_by_rating else "primary_release_date.desc",
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
