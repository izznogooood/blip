import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.core.database import Base, get_session
from app.main import app
from app.models.search_schedule import SearchSchedule  # noqa: F401  registers table
from app.models.settings import AppSettings  # noqa: F401  registers the table
from app.services.search_schedule_service import SearchScheduleService
from app.services.settings_service import SettingsService
from app.web.settings_routes import get_schedule_service, get_settings_service

# A clean env config (no .env read) so tests don't depend on the developer's
# ambient TMDB/Radarr environment variables.
_CLEAN_ENV = Settings(
    _env_file=None,
    tmdb_api_key=None,
    radarr_base_url=None,
    radarr_api_key=None,
    radarr_default_root_folder=None,
    radarr_default_quality_profile_id=None,
    radarr_default_minimum_availability="released",
)


@pytest.fixture
def client():
    """A TestClient backed by an isolated in-memory database and clean env."""
    # StaticPool keeps a single shared connection so every session sees the
    # same in-memory database across requests.
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_session():
        with factory() as s:
            yield s

    def override_settings_service():
        with factory() as s:
            yield SettingsService(s, env=_CLEAN_ENV)

    def override_schedule_service():
        with factory() as s:
            yield SearchScheduleService(s)

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_settings_service] = override_settings_service
    app.dependency_overrides[get_schedule_service] = override_schedule_service
    try:
        with TestClient(app) as test_client:
            test_client._factory = factory  # expose for assertions
            yield test_client
    finally:
        app.dependency_overrides.clear()


def test_settings_page_renders(client: TestClient) -> None:
    resp = client.get("/settings")
    assert resp.status_code == 200
    assert "Settings" in resp.text
    assert 'name="tmdb_api_key"' in resp.text
    assert 'name="radarr_default_minimum_availability"' in resp.text


def test_save_persists_and_redirects(client: TestClient) -> None:
    resp = client.post(
        "/settings",
        data={
            "radarr_base_url": "http://db:7878",
            "radarr_api_key": "secret-key",
            "radarr_default_root_folder": "/movies",
            "radarr_default_quality_profile_id": "4",
            "radarr_default_minimum_availability": "announced",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/settings?saved=true"

    with client._factory() as s:
        resolved = SettingsService(s).resolve()
    assert resolved.radarr_base_url == "http://db:7878"
    assert resolved.radarr_default_quality_profile_id == 4
    assert resolved.radarr_default_minimum_availability == "announced"


def test_secret_is_never_echoed_back(client: TestClient) -> None:
    client.post(
        "/settings",
        data={"radarr_api_key": "top-secret", "radarr_base_url": "http://db:7878"},
        follow_redirects=False,
    )
    page = client.get("/settings").text
    assert "top-secret" not in page


def test_blank_secret_keeps_existing_value(client: TestClient) -> None:
    client.post("/settings", data={"tmdb_api_key": "keep-me"}, follow_redirects=False)
    # Re-save with the secret field left blank — it must not be wiped.
    client.post(
        "/settings",
        data={"tmdb_api_key": "", "radarr_default_minimum_availability": "released"},
        follow_redirects=False,
    )
    with client._factory() as s:
        assert SettingsService(s).resolve().tmdb_api_key == "keep-me"


def test_radarr_options_error_preserves_defaults_as_hidden_inputs(
    client: TestClient,
) -> None:
    # No Radarr credentials configured → options can't load; saved defaults must
    # survive as hidden inputs so saving the form doesn't wipe them.
    resp = client.get("/settings/radarr-options")
    assert resp.status_code == 200
    assert 'type="hidden"' in resp.text
    assert 'name="radarr_default_root_folder"' in resp.text


def test_settings_page_renders_schedule_selector(client: TestClient) -> None:
    page = client.get("/settings").text
    assert 'name="radarr_search_schedule"' in page
    assert "Scheduled backlog search" in page
    assert "Run search now" in page


def test_save_persists_schedule(client: TestClient) -> None:
    client.post(
        "/settings",
        data={"radarr_search_schedule": "weekly"},
        follow_redirects=False,
    )
    with client._factory() as s:
        row = SearchScheduleService(s).get()
    assert row.schedule == "weekly"
    assert row.next_run_at is not None


def test_run_search_now_reports_unconfigured(client: TestClient) -> None:
    # Clean env → no Radarr configured → the manual run fails soft.
    resp = client.post("/settings/run-search-now")
    assert resp.status_code == 200
    assert "not configured" in resp.text.lower()


def test_run_search_now_triggers_when_configured(
    client: TestClient, monkeypatch
) -> None:
    from app.schemas.settings import ResolvedSettings
    from app.services.radarr_service import RadarrService

    monkeypatch.setattr(
        SettingsService,
        "resolve",
        lambda self: ResolvedSettings(
            radarr_base_url="http://radarr", radarr_api_key="key"
        ),
    )
    called: list[bool] = []
    monkeypatch.setattr(
        RadarrService, "search_missing", lambda self: called.append(True)
    )

    resp = client.post("/settings/run-search-now")
    assert resp.status_code == 200
    assert "triggered" in resp.text.lower()
    assert called == [True]
    with client._factory() as s:
        assert SearchScheduleService(s).get().last_result == "ok"
