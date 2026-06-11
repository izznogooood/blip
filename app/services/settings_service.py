from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.config import settings as env_settings
from app.models.settings import SETTINGS_ROW_ID, AppSettings
from app.schemas.settings import ResolvedSettings

# Fields that are both stored in the DB row and present on the env config, in
# the order they map onto :class:`ResolvedSettings`.
_FIELDS: tuple[str, ...] = (
    "tmdb_api_key",
    "radarr_base_url",
    "radarr_api_key",
    "radarr_default_root_folder",
    "radarr_default_quality_profile_id",
    "radarr_default_minimum_availability",
)


class SettingsService:
    """Read/write app settings, with environment variables as the fallback.

    A database value takes precedence; when it is unset (``None`` or empty),
    the corresponding environment variable is used (PRD §12 / ADR-004). The
    single settings row is created lazily on first save.
    """

    def __init__(self, session: Session, *, env: Settings = env_settings) -> None:
        self._session = session
        self._env = env

    def get_row(self) -> AppSettings | None:
        """Return the stored settings row, or ``None`` if never saved."""
        return self._session.get(AppSettings, SETTINGS_ROW_ID)

    def resolve(self) -> ResolvedSettings:
        """Return the effective settings (DB row overlaid on env config)."""
        row = self.get_row()
        values: dict[str, object] = {}
        for field in _FIELDS:
            stored = getattr(row, field, None) if row is not None else None
            values[field] = stored if stored not in (None, "") else getattr(
                self._env, field
            )
        return ResolvedSettings(**values)

    def save(self, values: dict[str, object]) -> AppSettings:
        """Upsert the settings row from ``values``.

        Only keys in ``_FIELDS`` are applied. Empty strings are stored as
        ``None`` so the value transparently falls back to the environment.
        """
        row = self.get_row()
        if row is None:
            row = AppSettings(id=SETTINGS_ROW_ID)
            self._session.add(row)
        for field in _FIELDS:
            if field not in values:
                continue
            value = values[field]
            if isinstance(value, str):
                value = value.strip() or None
            setattr(row, field, value)
        self._session.commit()
        return row
