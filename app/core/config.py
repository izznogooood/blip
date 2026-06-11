from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration sourced from environment variables.

    These act as the fallback layer described in the PRD; database-stored
    settings (added in a later milestone) will take precedence when present.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    blip_host: str = "0.0.0.0"
    blip_port: int = 8080

    database_url: str = "sqlite:///./data/blip.db"

    tmdb_api_key: str | None = None

    radarr_base_url: str | None = None
    radarr_api_key: str | None = None
    radarr_default_root_folder: str | None = None
    radarr_default_quality_profile_id: int | None = None
    radarr_default_minimum_availability: str = "released"


settings = Settings()
