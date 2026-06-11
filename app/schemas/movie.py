from pydantic import BaseModel

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
