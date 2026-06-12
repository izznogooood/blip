import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.radarr import RadarrStatus
from app.services.radarr_service import RadarrService
from app.services.settings_service import SettingsService
from app.web.routes import get_radarr_service


class _AddClient:
    """Radarr client stub recording the add payload it receives."""

    def __init__(self, *, has_file: bool = False, monitored: bool = True) -> None:
        self.added: dict | None = None
        self._result = {"hasFile": has_file, "monitored": monitored}

    def lookup_by_tmdb(self, tmdb_id: int) -> dict:
        return {"tmdbId": tmdb_id, "title": "Looked Up", "year": 2024}

    def add_movie(self, payload: dict) -> dict:
        self.added = payload
        return {**payload, **self._result}


# --- service ------------------------------------------------------------------


def test_add_builds_payload_and_returns_status() -> None:
    client = _AddClient(has_file=False, monitored=True)
    status = RadarrService(client).add(
        42,
        quality_profile_id=3,
        root_folder_path="/movies",
        minimum_availability="released",
        search=True,
    )
    assert status == RadarrStatus.MISSING  # monitored, no file yet
    assert client.added is not None
    assert client.added["qualityProfileId"] == 3
    assert client.added["rootFolderPath"] == "/movies"
    assert client.added["minimumAvailability"] == "released"
    assert client.added["monitored"] is True
    assert client.added["addOptions"] == {"searchForMovie": True}
    # Looked-up fields are preserved in the posted body.
    assert client.added["tmdbId"] == 42
    assert client.added["title"] == "Looked Up"


def test_add_without_search_sets_flag_false() -> None:
    client = _AddClient()
    RadarrService(client).add(
        1, quality_profile_id=1, root_folder_path="/movies", search=False
    )
    assert client.added["addOptions"] == {"searchForMovie": False}


# --- route integration --------------------------------------------------------


def _settings(monkeypatch) -> None:
    """Force resolved settings to provide a root folder + quality profile."""
    from app.schemas.settings import ResolvedSettings

    resolved = ResolvedSettings(
        radarr_base_url="http://radarr",
        radarr_api_key="key",
        radarr_default_root_folder="/movies",
        radarr_default_quality_profile_id=1,
        radarr_default_minimum_availability="released",
    )
    monkeypatch.setattr(SettingsService, "resolve", lambda self: resolved)


def test_add_route_renders_updated_card(monkeypatch) -> None:
    _settings(monkeypatch)
    client = _AddClient(has_file=False, monitored=True)
    app.dependency_overrides[get_radarr_service] = lambda: RadarrService(client)
    try:
        with TestClient(app) as http:
            response = http.post(
                "/movies/add",
                data={"id": 7, "title": "Test Movie", "search": "true"},
            )
        assert response.status_code == 200
        assert "Already in Radarr" in response.text  # in_radarr now true
        assert "Missing" in response.text  # status badge
        assert client.added["addOptions"] == {"searchForMovie": True}
    finally:
        app.dependency_overrides.clear()


def test_add_from_modal_closes_modal_and_updates_card_oob(monkeypatch) -> None:
    _settings(monkeypatch)
    client = _AddClient(has_file=False, monitored=True)
    app.dependency_overrides[get_radarr_service] = lambda: RadarrService(client)
    try:
        with TestClient(app) as http:
            response = http.post(
                "/movies/add",
                data={"id": 7, "title": "Test Movie", "search": "false", "source": "modal"},
            )
        assert response.status_code == 200
        # Success closes the modal: retarget the empty swap at #modal.
        assert response.headers["hx-retarget"] == "#modal"
        assert response.headers["hx-reswap"] == "innerHTML"
        # The grid card is updated out-of-band so it stays in sync.
        assert 'id="movie-card-7"' in response.text
        assert 'hx-swap-oob="true"' in response.text
        # The modal control area is not returned — the modal is closing.
        assert 'id="movie-actions-modal-7"' not in response.text
    finally:
        app.dependency_overrides.clear()


def test_add_from_modal_error_keeps_modal_open(monkeypatch) -> None:
    _settings(monkeypatch)

    class _Boom:
        def lookup_by_tmdb(self, tmdb_id: int) -> dict:
            request = httpx.Request("GET", "http://radarr/api/v3/movie/lookup/tmdb")
            raise httpx.ConnectError("down", request=request)

        def add_movie(self, payload: dict) -> dict:  # pragma: no cover
            raise AssertionError("should not be reached")

    app.dependency_overrides[get_radarr_service] = lambda: RadarrService(_Boom())
    try:
        with TestClient(app) as http:
            response = http.post(
                "/movies/add",
                data={"id": 7, "title": "Test Movie", "source": "modal"},
            )
        assert response.status_code == 200
        # No retarget: the modal stays open and shows the error + Add buttons.
        assert "hx-retarget" not in response.headers
        assert 'id="movie-actions-modal-7"' in response.text
        assert "Could not add the movie" in response.text
        assert "Add + Search" in response.text
    finally:
        app.dependency_overrides.clear()


def test_add_route_errors_when_radarr_unconfigured() -> None:
    app.dependency_overrides[get_radarr_service] = lambda: None
    try:
        with TestClient(app) as http:
            response = http.post(
                "/movies/add", data={"id": 7, "title": "Test Movie"}
            )
        assert response.status_code == 200
        assert "Radarr is not configured" in response.text
        assert "Add + Search" in response.text  # buttons remain for retry
    finally:
        app.dependency_overrides.clear()


def test_add_route_errors_without_defaults(monkeypatch) -> None:
    from app.schemas.settings import ResolvedSettings

    resolved = ResolvedSettings(
        radarr_base_url="http://radarr", radarr_api_key="key"
    )  # no root folder / profile
    monkeypatch.setattr(SettingsService, "resolve", lambda self: resolved)
    app.dependency_overrides[get_radarr_service] = lambda: RadarrService(_AddClient())
    try:
        with TestClient(app) as http:
            response = http.post(
                "/movies/add", data={"id": 7, "title": "Test Movie"}
            )
        assert response.status_code == 200
        assert "Settings" in response.text
        assert "Add + Search" in response.text
    finally:
        app.dependency_overrides.clear()
