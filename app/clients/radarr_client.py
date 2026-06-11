import httpx


class RadarrClient:
    """Thin HTTP wrapper around the Radarr v3 API.

    This client only performs HTTP calls and returns the raw decoded JSON.
    Mapping into Blip's internal schema and any business logic live in the
    service layer (see ``app/services``). The API key is sent as the
    ``X-Api-Key`` header so it never appears in a URL or log line.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        timeout: float = 10.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout
        # Injectable for tests (e.g. httpx.MockTransport); None uses the default.
        self._transport = transport

    def movies(self) -> list[dict]:
        """Return all movies currently in the Radarr library."""
        return self._get("/api/v3/movie")

    def quality_profiles(self) -> list[dict]:
        """Return the configured Radarr quality profiles."""
        return self._get("/api/v3/qualityprofile")

    def root_folders(self) -> list[dict]:
        """Return the configured Radarr root folders."""
        return self._get("/api/v3/rootfolder")

    def _get(self, path: str) -> list[dict]:
        with httpx.Client(
            base_url=self._base_url,
            timeout=self._timeout,
            transport=self._transport,
            headers={"X-Api-Key": self._api_key},
        ) as client:
            response = client.get(path)
            response.raise_for_status()
            return response.json()
