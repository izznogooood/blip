"""Tests for the loading indicators shown while HTMX requests are in flight.

Covers the two overlays on the main page: ``#list-loading`` (grid refresh)
and ``#modal-loading`` (poster click → synopsis modal, which fans out to TMDB
+ Radarr and can take seconds on a cold cache).
"""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.core.database import Base, get_session
from app.main import app
from app.services.movie_service import MovieService
from app.web.routes import get_movie_service
from app.web.settings_routes import get_settings_service
from app.services.settings_service import SettingsService


class _StubClient:
    """Minimal TMDB client stub returning one movie plus genres."""

    def now_playing(self, page: int = 1) -> dict:
        return {"results": [{"id": 1, "title": "A", "vote_average": 9.0}], "page": 1, "total_pages": 1}

    def upcoming(self, page: int = 1) -> dict:
        return self.now_playing(page)

    def discover(self, page: int = 1, params: dict | None = None) -> dict:
        return self.now_playing(page)

    def genres(self) -> dict:
        return {"genres": [{"id": 28, "name": "Action"}]}

    def movie_details(self, movie_id: int) -> dict:
        return {}


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
def client() -> Generator[TestClient, None, None]:
    """TestClient with an isolated DB and a stubbed TMDB service."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_session() -> Generator[Session, None, None]:
        with factory() as s:
            yield s

    def override_settings_service() -> Generator[SettingsService, None, None]:
        with factory() as s:
            yield SettingsService(s, env=_CLEAN_ENV)

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_settings_service] = override_settings_service
    app.dependency_overrides[get_movie_service] = lambda: MovieService(_StubClient())
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.clear()


def test_index_renders_modal_loading_overlay(client: TestClient) -> None:
    """The main page ships a full-screen modal loading overlay."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert 'id="modal-loading"' in resp.text
    # Full-screen, centred, dimming backdrop.
    assert "htmx-indicator fixed inset-0 z-40 flex items-center justify-center" in resp.text
    assert "bg-slate-900/80" in resp.text


def test_modal_loading_overlay_is_hidden_until_request_is_in_flight(client: TestClient) -> None:
    """The overlay is display:none by default (htmx-indicator toggles it)."""
    resp = client.get("/static/app.css")
    assert ".htmx-indicator { display: none !important; }" in resp.text
    assert ".htmx-indicator.htmx-request { display: flex !important; }" in resp.text


def test_modal_loading_overlay_is_a_sibling_of_the_modal_mount(client: TestClient) -> None:
    """The overlay must live outside #modal so the swap cannot wipe it."""
    html = client.get("/").text
    overlay_idx = html.index('id="modal-loading"')
    modal_idx = html.index('id="modal"')
    segment = html[overlay_idx:modal_idx]
    # Balanced <div>/</div> up to #modal ⇒ the overlay closed before it, i.e.
    # the two elements are siblings, not ancestor/descendant.
    assert segment.count("<div") == segment.count("</div>")


def test_poster_click_targets_the_modal_loading_overlay(client: TestClient) -> None:
    """Every poster button points hx-indicator at the modal overlay."""
    resp = client.get("/movies?list=in_theaters")
    assert resp.status_code == 200
    assert 'hx-get="/movies/1/modal"' in resp.text
    assert 'hx-indicator="#modal-loading"' in resp.text


def test_shared_spinner_partial_used_by_both_overlays(client: TestClient) -> None:
    """Both overlays render the same spinner body (single source of truth)."""
    resp = client.get("/")
    quip = "Waking up Radarr"
    assert resp.text.count(quip) == 2
    assert resp.text.count("animate-spin rounded-full border-4") == 2
