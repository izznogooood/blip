"""Tests for the responsive top navigation (Milestone 11, ADR-017).

Covers desktop nav, mobile drawer, Alpine state on <body>, and the
settings-page drawer (which should render tabs only on the main page).
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
from app.services.movie_service import MOVIE_LISTS, MovieService
from app.services.settings_service import SettingsService
from app.web.routes import get_movie_service
from app.web.settings_routes import get_settings_service


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _GenreStub:
    """Minimal TMDB client stub — only genres() is needed for nav tests."""

    def genres(self) -> dict:
        return {"genres": [{"id": 28, "name": "Action"}, {"id": 53, "name": "Thriller"}]}

    # Other TMDBClient methods — not called during GET / but must exist.
    def now_playing(self, page: int = 1) -> dict:
        return {"results": [], "page": 1, "total_pages": 1}

    def upcoming(self, page: int = 1) -> dict:
        return {"results": [], "page": 1, "total_pages": 1}

    def discover(self, page: int = 1, params: dict | None = None) -> dict:
        return {"results": [], "page": 1, "total_pages": 1}

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
def settings_client() -> Generator[TestClient, None, None]:
    """TestClient backed by an isolated in-memory database for settings tests."""
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
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Desktop nav (visible at md+)
# ---------------------------------------------------------------------------

def test_desktop_nav_renders_all_tabs() -> None:
    """Desktop tab bar contains all five list labels."""
    with TestClient(app) as client:
        resp = client.get("/")
    assert resp.status_code == 200
    for _, label in MOVIE_LISTS:
        assert label in resp.text


def test_desktop_nav_is_hidden_on_mobile() -> None:
    """Desktop nav carries the ``hidden md:flex`` responsive class."""
    with TestClient(app) as client:
        resp = client.get("/")
    assert 'hidden md:flex' in resp.text


def test_desktop_nav_tabs_have_htmx_attributes() -> None:
    """Desktop tab buttons carry hx-get pointing at the correct list."""
    with TestClient(app) as client:
        resp = client.get("/")
    for list_id, _ in MOVIE_LISTS:
        assert f'hx-get="/movies?list={list_id}"' in resp.text
    assert 'hx-target="#movie-list"' in resp.text


def test_desktop_nav_includes_tmdb_logo() -> None:
    """Desktop header includes the TMDB-powered-by logo."""
    with TestClient(app) as client:
        resp = client.get("/")
    assert 'blue_square.svg' in resp.text
    assert 'The Movie Database (TMDB)' in resp.text
    assert 'target="_blank"' in resp.text


def test_desktop_nav_includes_settings_link() -> None:
    """Desktop header includes a Settings link."""
    with TestClient(app) as client:
        resp = client.get("/")
    assert 'href="/settings"' in resp.text
    assert "Settings" in resp.text


# ---------------------------------------------------------------------------
# Mobile header / hamburger
# ---------------------------------------------------------------------------

def test_mobile_header_shows_on_small_viewports() -> None:
    """Mobile header row uses ``flex md:hidden`` to show only below md."""
    with TestClient(app) as client:
        resp = client.get("/")
    assert 'flex md:hidden' in resp.text


def test_mobile_header_has_hamburger_toggle() -> None:
    """Mobile header includes a hamburger button with Alpine toggle."""
    with TestClient(app) as client:
        resp = client.get("/")
    assert '@click="navOpen = !navOpen"' in resp.text
    assert 'aria-label="Toggle navigation"' in resp.text
    assert 'x-show="!navOpen"' in resp.text  # hamburger icon


def test_mobile_header_has_close_icon() -> None:
    """Mobile header toggle also shows an X icon when nav is open."""
    with TestClient(app) as client:
        resp = client.get("/")
    assert 'x-show="navOpen"' in resp.text  # X icon


# ---------------------------------------------------------------------------
# Mobile drawer
# ---------------------------------------------------------------------------

def test_mobile_drawer_renders() -> None:
    """Mobile drawer container and backdrop are present."""
    with TestClient(app) as client:
        resp = client.get("/")
    assert 'x-show="navOpen"' in resp.text
    assert 'md:hidden fixed inset-x-0 top-0 z-50' in resp.text
    assert 'z-40 bg-black/50' in resp.text  # backdrop


def test_mobile_drawer_renders_all_tabs() -> None:
    """Mobile drawer includes all five list labels."""
    with TestClient(app) as client:
        resp = client.get("/")
    for _, label in MOVIE_LISTS:
        assert label in resp.text


def test_mobile_drawer_tabs_have_htmx_and_redirect_logic() -> None:
    """Mobile tab buttons carry hx-get and the movie-list detection redirect."""
    with TestClient(app) as client:
        resp = client.get("/")
    for list_id, _ in MOVIE_LISTS:
        assert f'hx-get="/movies?list={list_id}"' in resp.text
    assert "document.getElementById('movie-list')" in resp.text
    assert "window.location.href = '/?list=" in resp.text


def test_mobile_drawer_has_tmdb_attribution() -> None:
    """Mobile drawer includes 'Powered by TMDB'. """
    with TestClient(app) as client:
        resp = client.get("/")
    assert "Powered by" in resp.text
    assert "themoviedb.org" in resp.text


def test_mobile_drawer_has_settings_link() -> None:
    """Mobile drawer includes a Settings link with active-state class."""
    with TestClient(app) as client:
        resp = client.get("/")
    assert 'href="/settings"' in resp.text
    assert "window.location.pathname === '/settings'" in resp.text


# ---------------------------------------------------------------------------
# Mobile drawer genre controls (rendered only when genres are available)
# ---------------------------------------------------------------------------

def test_mobile_genre_select_renders_when_genres_available() -> None:
    """Mobile genre dropdown renders when the service returns genres."""
    app.dependency_overrides[get_movie_service] = lambda: MovieService(_GenreStub())
    try:
        with TestClient(app) as client:
            resp = client.get("/")
        assert 'id="genre-select-mobile"' in resp.text
        assert "Action" in resp.text
        assert "Thriller" in resp.text
    finally:
        app.dependency_overrides.clear()


def test_mobile_sort_checkbox_renders_when_genres_available() -> None:
    """Mobile 'By rating' checkbox renders when genres are available."""
    app.dependency_overrides[get_movie_service] = lambda: MovieService(_GenreStub())
    try:
        with TestClient(app) as client:
            resp = client.get("/")
        assert 'id="sort-checkbox-mobile"' in resp.text
        assert "By rating" in resp.text
        assert ':disabled="!activeGenre"' in resp.text
    finally:
        app.dependency_overrides.clear()


def test_mobile_genre_select_filters_empty_value() -> None:
    """Mobile genre select does not fire when 'All Genres' is selected."""
    app.dependency_overrides[get_movie_service] = lambda: MovieService(_GenreStub())
    try:
        with TestClient(app) as client:
            resp = client.get("/")
        assert 'hx-trigger="change[this.value != \'\']"' in resp.text
    finally:
        app.dependency_overrides.clear()


def test_desktop_genre_select_filters_empty_value() -> None:
    """Desktop genre select does not fire when 'All Genres' is selected."""
    app.dependency_overrides[get_movie_service] = lambda: MovieService(_GenreStub())
    try:
        with TestClient(app) as client:
            resp = client.get("/")
        assert 'hx-trigger="change[this.value != \'\']"' in resp.text
    finally:
        app.dependency_overrides.clear()


def test_desktop_genre_select_has_htmx_attributes() -> None:
    """Desktop genre <select> carries its own HTMX attributes (no from:)."""
    app.dependency_overrides[get_movie_service] = lambda: MovieService(_GenreStub())
    try:
        with TestClient(app) as client:
            resp = client.get("/")
        assert 'id="genre-select"' in resp.text
        assert 'hx-get="/movies"' in resp.text
        assert 'hx-target="#movie-list"' in resp.text
        assert 'hx-trigger="change[this.value != \'\']"' in resp.text
        assert 'hx-include="#genre-select, #sort-checkbox"' in resp.text
    finally:
        app.dependency_overrides.clear()


def test_desktop_sort_checkbox_has_htmx_attributes() -> None:
    """Desktop sort checkbox carries its own HTMX attributes (no from:)."""
    app.dependency_overrides[get_movie_service] = lambda: MovieService(_GenreStub())
    try:
        with TestClient(app) as client:
            resp = client.get("/")
        assert 'id="sort-checkbox"' in resp.text
        assert 'hx-get="/movies"' in resp.text
        assert 'hx-target="#movie-list"' in resp.text
        assert 'hx-trigger="change"' in resp.text
        assert 'hx-include="#genre-select, #sort-checkbox"' in resp.text
    finally:
        app.dependency_overrides.clear()


def test_mobile_genre_controls_share_hx_include() -> None:
    """Mobile genre select and checkbox both include each other."""
    app.dependency_overrides[get_movie_service] = lambda: MovieService(_GenreStub())
    try:
        with TestClient(app) as client:
            resp = client.get("/")
        assert 'hx-include="#genre-select-mobile, #sort-checkbox-mobile"' in resp.text
    finally:
        app.dependency_overrides.clear()


def test_mobile_genre_select_not_present_when_service_unconfigured() -> None:
    """Mobile genre dropdown is absent when the movie service is None."""
    app.dependency_overrides[get_movie_service] = lambda: None
    try:
        with TestClient(app) as client:
            resp = client.get("/")
        assert 'id="genre-select-mobile"' not in resp.text
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Alpine <body> state
# ---------------------------------------------------------------------------

def test_body_has_alpine_x_data() -> None:
    """<body> includes x-data with all nav state keys."""
    with TestClient(app) as client:
        resp = client.get("/")
    assert 'x-data="{ navOpen: false, activeTab:' in resp.text
    assert "activeGenre" in resp.text
    assert "sortByRating" in resp.text


def test_body_has_scroll_lock_binding() -> None:
    """<body> has :class binding for overflow-hidden when nav is open."""
    with TestClient(app) as client:
        resp = client.get("/")
    assert ':class="navOpen ? \'overflow-hidden\' : \'\'"' in resp.text


def test_body_has_escape_key_handler() -> None:
    """<body> closes the drawer on Escape key."""
    with TestClient(app) as client:
        resp = client.get("/")
    assert "@keydown.escape.window" in resp.text or '@keydown.escape.window="navOpen = false"' in resp.text


# ---------------------------------------------------------------------------
# `/x-cloak` in CSS prevents Alpine flicker
# ---------------------------------------------------------------------------

def test_x_cloak_css_loaded() -> None:
    """The app CSS includes the [x-cloak] rule."""
    with TestClient(app) as client:
        resp = client.get("/static/app.css")
    assert "[x-cloak]" in resp.text
    assert "display: none" in resp.text


# ---------------------------------------------------------------------------
# Settings page — drawer renders WITHOUT list tabs (regression guard,
# see PR #10 review finding #1)
# ---------------------------------------------------------------------------

def test_settings_page_drawer_has_no_list_tabs(settings_client: TestClient) -> None:
    """Settings page mobile drawer does NOT render list tabs.

    The settings page provides no ``lists`` template variable, so the
    ``{% if lists %}`` block in base.html is skipped.
    """
    resp = settings_client.get("/settings")
    assert resp.status_code == 200
    # List labels must not appear in the drawer HTML.
    for _, label in MOVIE_LISTS:
        assert label not in resp.text


def test_settings_page_drawer_still_has_settings_link(settings_client: TestClient) -> None:
    """Settings page drawer still shows the Settings link (outside ``{% if lists %}``)."""
    resp = settings_client.get("/settings")
    assert resp.status_code == 200
    assert 'href="/settings"' in resp.text
    assert "Settings" in resp.text


def test_settings_page_drawer_still_has_tmdb(settings_client: TestClient) -> None:
    """Settings page drawer still shows the TMDB attribution (outside ``{% if lists %}``)."""
    resp = settings_client.get("/settings")
    assert resp.status_code == 200
    assert "themoviedb.org" in resp.text


def test_settings_page_drawer_still_has_back_link(settings_client: TestClient) -> None:
    """Settings page includes the ``← Back`` link to the main page."""
    resp = settings_client.get("/settings")
    assert resp.status_code == 200
    assert "Back" in resp.text or "back" in resp.text
