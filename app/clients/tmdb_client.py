import httpx

TMDB_BASE_URL = "https://api.themoviedb.org/3"


class TMDBClient:
    """Thin HTTP wrapper around the TMDB v3 API.

    This client only performs HTTP calls and returns the raw decoded JSON.
    Mapping into Blip's internal schema and any business logic live in the
    service layer (see ``app/services``).
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = TMDB_BASE_URL,
        region: str = "US",
        timeout: float = 10.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._region = region
        self._timeout = timeout
        # Injectable for tests (e.g. httpx.MockTransport); None uses the default.
        self._transport = transport

    def now_playing(self, page: int = 1) -> dict:
        """Return the TMDB "now playing" (In Theaters) payload for ``page``."""
        return self._get(
            "/movie/now_playing", {"page": page, "region": self._region}
        )

    def upcoming(self, page: int = 1) -> dict:
        """Return the TMDB "upcoming" (Upcoming Theatrical) payload for ``page``."""
        return self._get(
            "/movie/upcoming", {"page": page, "region": self._region}
        )

    def movie_details(self, movie_id: int) -> dict:
        """Return the TMDB details payload for ``movie_id``.

        ``videos`` is appended in the same request so the trailer can be
        extracted without a second round-trip.
        """
        return self._get(
            f"/movie/{movie_id}", {"append_to_response": "videos"}
        )

    def discover(self, page: int = 1, params: dict | None = None) -> dict:
        """Return a TMDB ``/discover/movie`` payload for ``page``.

        ``params`` carries discover-specific filters (release type, date range,
        sort). The region is included so regional release-date filtering applies.
        """
        query = {"page": page, "region": self._region, **(params or {})}
        return self._get("/discover/movie", query)

    def _get(self, path: str, params: dict) -> dict:
        query = {"api_key": self._api_key, **params}
        with httpx.Client(
            base_url=self._base_url,
            timeout=self._timeout,
            transport=self._transport,
        ) as client:
            response = client.get(path, params=query)
            response.raise_for_status()
            return response.json()
