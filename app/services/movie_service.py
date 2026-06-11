from app.clients.tmdb_client import TMDBClient
from app.schemas.movie import Movie


class MovieService:
    """Business logic for fetching and shaping movie lists.

    Calls the TMDB client and maps raw responses into Blip's internal
    :class:`Movie` schema. Future milestones will merge Radarr status here.
    """

    def __init__(self, client: TMDBClient) -> None:
        self._client = client

    def in_theaters(self, page: int = 1) -> list[Movie]:
        payload = self._client.now_playing(page=page)
        return self._map_results(payload)

    @staticmethod
    def _map_results(payload: dict) -> list[Movie]:
        results = payload.get("results") or []
        return [Movie.from_tmdb(item) for item in results]
