from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# Settings live in a single row (see ADR-011). This is its fixed primary key.
SETTINGS_ROW_ID = 1


class AppSettings(Base):
    """Database-stored application settings — a single row (id=1).

    Every column is nullable: a ``None``/empty value means "not configured
    here", and the resolver falls back to the environment-based config
    (:class:`app.core.config.Settings`). Secrets are stored here only when the
    user enters them in the UI; they are never rendered back into HTML.
    """

    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=SETTINGS_ROW_ID)

    tmdb_api_key: Mapped[str | None] = mapped_column(String, nullable=True)
    radarr_base_url: Mapped[str | None] = mapped_column(String, nullable=True)
    radarr_api_key: Mapped[str | None] = mapped_column(String, nullable=True)
    radarr_default_root_folder: Mapped[str | None] = mapped_column(String, nullable=True)
    radarr_default_quality_profile_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    radarr_default_minimum_availability: Mapped[str | None] = mapped_column(
        String, nullable=True
    )
