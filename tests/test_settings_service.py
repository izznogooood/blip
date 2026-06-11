import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.database import Base
from app.models.settings import AppSettings  # noqa: F401  registers the table
from app.services.settings_service import SettingsService


@pytest.fixture
def session() -> Session:
    """An isolated in-memory SQLite session with the settings table created."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as s:
        yield s


def _env(**overrides) -> Settings:
    """An env-config instance with no .env file read, plus optional overrides."""
    base = dict(
        tmdb_api_key=None,
        radarr_base_url=None,
        radarr_api_key=None,
        radarr_default_root_folder=None,
        radarr_default_quality_profile_id=None,
        radarr_default_minimum_availability="released",
    )
    base.update(overrides)
    return Settings(_env_file=None, **base)


def test_resolve_uses_env_when_no_row(session: Session) -> None:
    env = _env(tmdb_api_key="env-key", radarr_base_url="http://env:7878")
    service = SettingsService(session, env=env)

    resolved = service.resolve()

    assert resolved.tmdb_api_key == "env-key"
    assert resolved.radarr_base_url == "http://env:7878"
    assert resolved.radarr_default_minimum_availability == "released"


def test_db_value_overrides_env(session: Session) -> None:
    env = _env(tmdb_api_key="env-key")
    service = SettingsService(session, env=env)

    service.save({"tmdb_api_key": "db-key"})

    assert service.resolve().tmdb_api_key == "db-key"


def test_empty_db_value_falls_back_to_env(session: Session) -> None:
    env = _env(radarr_base_url="http://env:7878")
    service = SettingsService(session, env=env)

    # An empty string is stored as None and must not shadow the env value.
    service.save({"radarr_base_url": "   "})

    row = service.get_row()
    assert row.radarr_base_url is None
    assert service.resolve().radarr_base_url == "http://env:7878"


def test_save_is_an_upsert(session: Session) -> None:
    service = SettingsService(session, env=_env())

    service.save({"radarr_default_quality_profile_id": 3})
    service.save({"radarr_default_root_folder": "/movies"})

    resolved = service.resolve()
    assert resolved.radarr_default_quality_profile_id == 3
    assert resolved.radarr_default_root_folder == "/movies"
    # Only one settings row ever exists.
    assert session.query(AppSettings).count() == 1


def test_save_ignores_unknown_keys(session: Session) -> None:
    service = SettingsService(session, env=_env())

    service.save({"radarr_base_url": "http://db:7878", "bogus": "x"})

    row = service.get_row()
    assert row.radarr_base_url == "http://db:7878"
    assert not hasattr(row, "bogus")


def test_radarr_configured_requires_both_url_and_key(session: Session) -> None:
    service = SettingsService(session, env=_env(radarr_base_url="http://env:7878"))
    assert service.resolve().radarr_configured is False

    service.save({"radarr_api_key": "k"})
    assert service.resolve().radarr_configured is True
