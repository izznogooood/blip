from collections.abc import Iterable

from app.clients.radarr_client import RadarrClient
from app.schemas.movie import Movie
from app.schemas.radarr import (
    QualityProfile,
    RadarrStatus,
    RootFolder,
    status_from_radarr,
)


class RadarrService:
    """Business logic over the Radarr library.

    Fetches the library once and exposes a TMDB-id → status lookup so movie
    cards can show whether a movie already exists in Radarr. Quality profiles
    and root folders are surfaced here too for the settings/add milestones.
    """

    def __init__(self, client: RadarrClient) -> None:
        self._client = client

    def statuses_by_tmdb_id(self) -> dict[int, RadarrStatus]:
        """Return a map of TMDB id → :class:`RadarrStatus` for library movies.

        Movies without a ``tmdbId`` are skipped (they can't be matched to a
        TMDB list entry). On a duplicate tmdbId the first wins.
        """
        statuses: dict[int, RadarrStatus] = {}
        for movie in self._client.movies():
            tmdb_id = movie.get("tmdbId")
            if tmdb_id is None:
                continue
            statuses.setdefault(int(tmdb_id), status_from_radarr(movie))
        return statuses

    def annotate(self, movies: Iterable[Movie]) -> None:
        """Set ``radarr_status`` on each movie present in the Radarr library.

        Movies not in Radarr are left as ``None`` (addable). One Radarr call is
        made regardless of how many movies are passed.
        """
        statuses = self.statuses_by_tmdb_id()
        for movie in movies:
            movie.radarr_status = statuses.get(movie.id)

    def quality_profiles(self) -> list[QualityProfile]:
        return [QualityProfile.from_radarr(p) for p in self._client.quality_profiles()]

    def root_folders(self) -> list[RootFolder]:
        return [RootFolder.from_radarr(f) for f in self._client.root_folders()]
