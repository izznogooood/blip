from pydantic import BaseModel

from app.schemas.radarr import RadarrStatus

# Poster image base URL. w500 is a good balance of quality and size for cards.
TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"


class Movie(BaseModel):
    """Blip's internal representation of a movie, decoupled from TMDB's shape."""

    id: int
    title: str
    year: int | None = None
    rating: float | None = None
    poster_url: str | None = None
    overview: str = ""
    # Set by RadarrService.annotate() when the movie exists in Radarr; None
    # means it is not in the library (and is therefore addable).
    radarr_status: RadarrStatus | None = None

    @property
    def in_radarr(self) -> bool:
        return self.radarr_status is not None

    @classmethod
    def from_tmdb(cls, data: dict) -> "Movie":
        """Map a single TMDB movie result into a :class:`Movie`.

        Tolerant of missing/partial fields so that incomplete TMDB entries do
        not break rendering.
        """
        poster_path = data.get("poster_path")
        return cls(
            id=data["id"],
            title=data.get("title") or data.get("original_title") or "Untitled",
            year=_parse_year(data.get("release_date")),
            rating=_normalize_rating(data.get("vote_average")),
            poster_url=(
                f"{TMDB_IMAGE_BASE_URL}{poster_path}" if poster_path else None
            ),
            overview=data.get("overview") or "",
        )


class MovieDetail(BaseModel):
    """Detailed movie info for the synopsis modal (PRD §10)."""

    id: int
    title: str
    year: int | None = None
    rating: float | None = None
    poster_url: str | None = None
    overview: str = ""
    release_date: str | None = None
    trailer_url: str | None = None

    @classmethod
    def from_tmdb(cls, data: dict) -> "MovieDetail":
        """Map a TMDB ``/movie/{id}?append_to_response=videos`` payload."""
        poster_path = data.get("poster_path")
        release_date = data.get("release_date") or None
        youtube_key = _trailer_key(data.get("videos"))
        return cls(
            id=data["id"],
            title=data.get("title") or data.get("original_title") or "Untitled",
            year=_parse_year(release_date),
            rating=_normalize_rating(data.get("vote_average")),
            poster_url=(
                f"{TMDB_IMAGE_BASE_URL}{poster_path}" if poster_path else None
            ),
            overview=data.get("overview") or "",
            release_date=release_date,
            trailer_url=(
                f"https://www.youtube.com/watch?v={youtube_key}"
                if youtube_key
                else None
            ),
        )


class MoviePage(BaseModel):
    """A single page of mapped movies plus TMDB pagination metadata."""

    movies: list[Movie]
    page: int = 1
    total_pages: int = 1

    @property
    def has_more(self) -> bool:
        return self.page < self.total_pages

    @classmethod
    def from_tmdb(cls, payload: dict) -> "MoviePage":
        results = payload.get("results") or []
        return cls(
            movies=[Movie.from_tmdb(item) for item in results],
            page=payload.get("page") or 1,
            total_pages=payload.get("total_pages") or 1,
        )


def _trailer_key(videos: dict | None) -> str | None:
    """Return the YouTube key of the best trailer in a TMDB videos block.

    Prefers an official "Trailer", then any "Trailer", then any "Teaser";
    only YouTube-hosted videos are considered (PRD §10). Returns ``None`` when
    no usable trailer is present.
    """
    results = (videos or {}).get("results") or []
    youtube = [v for v in results if v.get("site") == "YouTube" and v.get("key")]

    def pick(predicate) -> str | None:
        for video in youtube:
            if predicate(video):
                return video["key"]
        return None

    return (
        pick(lambda v: v.get("type") == "Trailer" and v.get("official"))
        or pick(lambda v: v.get("type") == "Trailer")
        or pick(lambda v: v.get("type") == "Teaser")
    )


def _parse_year(release_date: str | None) -> int | None:
    """Extract the year from a TMDB ``YYYY-MM-DD`` release date."""
    if not release_date:
        return None
    head = release_date.split("-", 1)[0]
    try:
        return int(head)
    except ValueError:
        return None


def _normalize_rating(vote_average: float | int | None) -> float | None:
    """Round the TMDB rating to one decimal; treat 0/None as no rating."""
    if not vote_average:
        return None
    return round(float(vote_average), 1)
