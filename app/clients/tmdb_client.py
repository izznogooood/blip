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
