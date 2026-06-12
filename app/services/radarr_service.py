from collections.abc import Iterable

from app.clients.radarr_client import RadarrClient
from app.schemas.movie import Movie
from app.schemas.radarr import (
    QualityProfile,
    RadarrStatus,
    RootFolder,
    status_from_radarr,
)
from app.services.cache_service import CacheService, RADARR_CACHE_TTL


class RadarrService:
    """Business logic over the Radarr library.

    Fetches the library once and exposes a TMDB-id → status lookup so movie
    cards can show whether a movie already exists in Radarr. Quality profiles
    and root folders are surfaced here too for the settings/add milestones.
    """

    def __init__(self, client: RadarrClient, *, cache: CacheService | None = None) -> None:
        self._client = client
        self._cache = cache

    def statuses_by_tmdb_id(
        self, *, force_refresh: bool = False
    ) -> dict[int, RadarrStatus]:
        """Return a map of TMDB id → :class:`RadarrStatus` for library movies.

        Movies without a ``tmdbId`` are skipped (they can't be matched to a
        TMDB list entry). On a duplicate tmdbId the first wins.
        """
        if self._cache is not None and not force_refresh:
            cached = self._cache.get("radarr:statuses")
            if cached is not None:
                return {int(k): RadarrStatus(v) for k, v in cached.items()}

        statuses: dict[int, RadarrStatus] = {}
        for movie in self._client.movies():
            tmdb_id = movie.get("tmdbId")
            if tmdb_id is None:
                continue
            statuses.setdefault(int(tmdb_id), status_from_radarr(movie))
        if self._cache is not None:
            self._cache.set(
                "radarr:statuses",
                {str(k): v.value for k, v in statuses.items()},
                RADARR_CACHE_TTL,
            )
        return statuses

    def annotate(self, movies: Iterable[Movie], *, force_refresh: bool = False) -> None:
        """Set ``radarr_status`` on each movie present in the Radarr library.

        Movies not in Radarr are left as ``None`` (addable). One Radarr call is
        made regardless of how many movies are passed.
        """
        statuses = self.statuses_by_tmdb_id(force_refresh=force_refresh)
        for movie in movies:
            movie.radarr_status = statuses.get(movie.id)

    def add(
        self,
        tmdb_id: int,
        *,
        quality_profile_id: int,
        root_folder_path: str,
        minimum_availability: str = "released",
        search: bool = False,
    ) -> RadarrStatus:
        """Add a movie to Radarr and return its resulting status.

        The full movie body is fetched from Radarr's lookup endpoint (which
        supplies title, year, images, etc.) and augmented with Blip's add
        options. ``search=True`` tells Radarr to search immediately on add via
        ``addOptions.searchForMovie`` (Add + Search), resolving PRD §25 #3/#4.
        """
        payload = self._client.lookup_by_tmdb(tmdb_id)
        payload.update(
            {
                "qualityProfileId": quality_profile_id,
                "rootFolderPath": root_folder_path,
                "minimumAvailability": minimum_availability,
                "monitored": True,
                "addOptions": {"searchForMovie": search},
            }
        )
        added = self._client.add_movie(payload)
        return status_from_radarr(added)

    def quality_profiles(self) -> list[QualityProfile]:
        return [QualityProfile.from_radarr(p) for p in self._client.quality_profiles()]

    def root_folders(self) -> list[RootFolder]:
        return [RootFolder.from_radarr(f) for f in self._client.root_folders()]
