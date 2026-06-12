import logging
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.clients.radarr_client import RadarrClient
from app.clients.tmdb_client import TMDBClient
from app.core.database import get_session
from app.schemas.movie import Movie
from app.services.cache_service import CacheService
from app.services.movie_service import (
    LIST_DESCRIPTIONS,
    MOVIE_LISTS,
    MovieService,
    UnknownListError,
)
from app.services.radarr_service import RadarrService
from app.services.settings_service import SettingsService

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter()


def get_movie_service(
    session: Session = Depends(get_session),
) -> MovieService | None:
    """Build a MovieService from resolved settings, or None if unconfigured.

    Settings resolve DB-stored values over environment fallbacks (ADR-011), so
    a TMDB key entered in the UI takes effect without a restart.
    """
    resolved = SettingsService(session).resolve()
    if not resolved.tmdb_api_key:
        return None
    return MovieService(
        TMDBClient(resolved.tmdb_api_key), cache=CacheService(session)
    )


def get_radarr_service(
    session: Session = Depends(get_session),
) -> RadarrService | None:
    """Build a RadarrService from resolved settings, or None if unconfigured."""
    resolved = SettingsService(session).resolve()
    if not resolved.radarr_configured:
        return None
    return RadarrService(
        RadarrClient(resolved.radarr_base_url, resolved.radarr_api_key)
    )


@router.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "index.html", {"app_name": "Blip", "lists": MOVIE_LISTS}
    )


def _annotate_radarr(
    movies: list, radarr: RadarrService | None, *, list_id: str, page: int
) -> None:
    """Merge Radarr status onto movies, failing soft if Radarr is unavailable.

    A Radarr outage must not break browsing: on error the movies keep their
    default (no status) and the grid still renders.
    """
    if radarr is None:
        return
    try:
        radarr.annotate(movies)
    except httpx.HTTPError as exc:
        logger.warning(
            "Radarr lookup failed: %s (list=%s page=%s) — cards shown without status",
            type(exc).__name__,
            list_id,
            page,
        )


def _quality_profiles(radarr: RadarrService | None) -> list:
    """Fetch Radarr quality profiles for the per-movie override dropdown.

    Fail-soft: a Radarr outage or missing config yields an empty list, in
    which case the Add form just uses the configured default profile.
    """
    if radarr is None:
        return []
    try:
        return radarr.quality_profiles()
    except httpx.HTTPError:
        return []


@router.get("/movies", response_class=HTMLResponse)
def movies(
    request: Request,
    list: str = "in_theaters",
    page: int = 1,
    refresh: bool = False,
    session: Session = Depends(get_session),
    service: MovieService | None = Depends(get_movie_service),
    radarr: RadarrService | None = Depends(get_radarr_service),
) -> HTMLResponse:
    """Return a movie grid partial for the given list (HTMX endpoint).

    Page 1 returns the full grid (used for initial load and tab switches);
    later pages return an append fragment whose cards are inserted into the
    existing grid and whose Load More button is swapped out-of-band.
    """
    resolved = SettingsService(session).resolve()
    context: dict[str, object] = {
        "movies": [],
        "error": None,
        "list_id": list,
        "page_data": None,
        "caption": LIST_DESCRIPTIONS.get(list),
        "quality_profiles": _quality_profiles(radarr),
        "default_quality_profile_id": resolved.radarr_default_quality_profile_id,
    }

    if service is None:
        context["error"] = "TMDB API key is not configured."
        return templates.TemplateResponse(request, "partials/movie_grid.html", context)

    try:
        page_data = service.movies(list, page=page, force_refresh=refresh)
        _annotate_radarr(page_data.movies, radarr, list_id=list, page=page)
        context["movies"] = page_data.movies
        context["page_data"] = page_data
        template = (
            "partials/movie_grid.html" if page <= 1 else "partials/movie_append.html"
        )
        return templates.TemplateResponse(request, template, context)
    except UnknownListError:
        context["error"] = f"Unknown list: {list}."
    except httpx.HTTPStatusError as exc:
        # Log status + path only — never the full URL, which carries the API key.
        logger.warning(
            "TMDB request failed: HTTP %s for %s (list=%s page=%s)",
            exc.response.status_code,
            exc.request.url.path,
            list,
            page,
        )
        if exc.response.status_code == 401:
            context["error"] = "TMDB API key is missing or invalid. Check your settings."
        else:
            context["error"] = "Could not load movies from TMDB right now."
    except httpx.HTTPError as exc:
        logger.warning(
            "TMDB request failed: %s (list=%s page=%s)",
            type(exc).__name__,
            list,
            page,
        )
        context["error"] = "Could not load movies from TMDB right now."

    return templates.TemplateResponse(request, "partials/movie_grid.html", context)


@router.post("/movies/add", response_class=HTMLResponse)
def add_movie(
    request: Request,
    id: int = Form(...),
    title: str = Form(...),
    year: int | None = Form(None),
    rating: float | None = Form(None),
    poster_url: str | None = Form(None),
    search: bool = Form(False),
    quality_profile_id: int | None = Form(None),
    session: Session = Depends(get_session),
    radarr: RadarrService | None = Depends(get_radarr_service),
) -> HTMLResponse:
    """Add a movie to Radarr and return the refreshed card (HTMX endpoint).

    The card's hidden fields carry just enough to re-render it; Radarr add
    options (profile, root folder, minimum availability) come from settings,
    with the quality profile overridable per movie. On success the card is
    re-rendered with its new status; on failure it keeps the Add buttons and
    shows an inline error (PRD §15).
    """
    movie = Movie(
        id=id, title=title, year=year, rating=rating, poster_url=poster_url
    )
    context: dict[str, object] = {"movie": movie, "add_error": None}

    if radarr is None:
        context["add_error"] = "Radarr is not configured. Check your settings."
        return templates.TemplateResponse(
            request, "partials/movie_card.html", context
        )

    resolved = SettingsService(session).resolve()
    profile_id = quality_profile_id or resolved.radarr_default_quality_profile_id
    root_folder = resolved.radarr_default_root_folder
    if not profile_id or not root_folder:
        context["add_error"] = (
            "Set a default root folder and quality profile in Settings first."
        )
        return templates.TemplateResponse(
            request, "partials/movie_card.html", context
        )

    try:
        movie.radarr_status = radarr.add(
            movie.id,
            quality_profile_id=profile_id,
            root_folder_path=root_folder,
            minimum_availability=resolved.radarr_default_minimum_availability,
            search=search,
        )
    except httpx.HTTPError as exc:
        logger.warning(
            "Radarr add failed: %s (tmdb_id=%s search=%s)",
            type(exc).__name__,
            movie.id,
            search,
        )
        context["add_error"] = "Could not add the movie to Radarr. Please try again."

    return templates.TemplateResponse(request, "partials/movie_card.html", context)


@router.get("/health")
def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})
