from pydantic import BaseModel

# Minimum availability values accepted by Radarr (PRD §11). Offered as the
# options in the settings dropdown; "released" is the default.
MINIMUM_AVAILABILITY_OPTIONS: list[str] = ["announced", "inCinemas", "released"]


class ResolvedSettings(BaseModel):
    """Effective settings after overlaying the database row on env defaults.

    This is what the rest of the app reads: a single, already-resolved view so
    callers never have to know whether a value came from the database or the
    environment.
    """

    tmdb_api_key: str | None = None
    radarr_base_url: str | None = None
    radarr_api_key: str | None = None
    radarr_default_root_folder: str | None = None
    radarr_default_quality_profile_id: int | None = None
    radarr_default_minimum_availability: str = "released"

    @property
    def radarr_configured(self) -> bool:
        """Whether a Radarr base URL and API key are both available."""
        return bool(self.radarr_base_url and self.radarr_api_key)
