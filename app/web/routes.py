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
        RadarrClient(resolved.radarr_base_url, resolved.radarr_api_key),
        cache=CacheService(session),
    )


@router.get("/", response_class=HTMLResponse)
def index(
    request: Request,
    session: Session = Depends(get_session),
    service: MovieService | None = Depends(get_movie_service),
) -> HTMLResponse:
    genres: list = []
    if service is not None:
        try:
            genres = service.genres()
        except httpx.HTTPError:
            logger.warning("Failed to fetch genre list")
    return templates.TemplateResponse(
        request,
        "index.html",
        {"app_name": "Blip", "lists": MOVIE_LISTS, "genres": genres},
    )


def _annotate_radarr(
    movies: list,
    radarr: RadarrService | None,
    *,
    list_id: str,
    page: int,
    force_refresh: bool = False,
) -> None:
    """Merge Radarr status onto movies, failing soft if Radarr is unavailable.

    A Radarr outage must not break browsing: on error the movies keep their
    default (no status) and the grid still renders.
    """
    if radarr is None:
        return
    try:
        radarr.annotate(movies, force_refresh=force_refresh)
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


def _genre_caption(service: MovieService | None, genre_id: int) -> str | None:
    """Look up the genre name from the cached genre map for the caption."""
    if service is None:
        return None
    try:
        name = service.genre_map().get(genre_id)
        if name:
            return f"{name} — new movies released in the last 180 days"
    except httpx.HTTPError:
        pass
    return None


@router.get("/movies", response_class=HTMLResponse)
def movies(
    request: Request,
    list: str = "in_theaters",
    page: int = 1,
    refresh: bool = False,
    genre_id: int | None = None,
    sort_by_rating: bool = False,
    session: Session = Depends(get_session),
    service: MovieService | None = Depends(get_movie_service),
    radarr: RadarrService | None = Depends(get_radarr_service),
) -> HTMLResponse:
    """Return a movie grid partial for the given list or genre (HTMX endpoint).

    When ``genre_id`` is provided the grid shows movies from that genre;
    otherwise it shows a named list. Page 1 returns the full grid; later pages
    return an append fragment.
    """
    resolved = SettingsService(session).resolve()
    context: dict[str, object] = {
        "movies": [],
        "error": None,
        "list_id": list,
        "genre_id": genre_id,
        "sort_by_rating": sort_by_rating,
        "page_data": None,
        "caption": (
            _genre_caption(service, genre_id)
            if genre_id
            else LIST_DESCRIPTIONS.get(list)
        ),
        "quality_profiles": _quality_profiles(radarr),
        "default_quality_profile_id": resolved.radarr_default_quality_profile_id,
    }

    if service is None:
        context["error"] = "TMDB API key is not configured."
        return templates.TemplateResponse(request, "partials/movie_grid.html", context)

    try:
        if genre_id:
            page_data = service.genre_movies(genre_id, page=page, sort_by_rating=sort_by_rating, force_refresh=refresh)
        else:
            page_data = service.movies(list, page=page, force_refresh=refresh)
        _annotate_radarr(
            page_data.movies,
            radarr,
            list_id=list,
            page=page,
            force_refresh=refresh or page <= 1,
        )
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
    source: str = Form("card"),
    session: Session = Depends(get_session),
    radarr: RadarrService | None = Depends(get_radarr_service),
) -> HTMLResponse:
    """Add a movie to Radarr and return the refreshed controls (HTMX endpoint).

    Add can be triggered from a card or from the synopsis modal (``source``).
    The hidden fields carry just enough to re-render; Radarr add options
    (profile, root folder, minimum availability) come from settings, with the
    quality profile overridable per movie. On success the controls re-render
    with the new status; on failure they keep the Add buttons and show an
    inline error (PRD §15). Adds from the modal also update the grid card
    out-of-band so it greys out without a reload.
    """
    movie = Movie(
        id=id, title=title, year=year, rating=rating, poster_url=poster_url
    )
    add_error: str | None = None

    if radarr is None:
        add_error = "Radarr is not configured. Check your settings."
    else:
        resolved = SettingsService(session).resolve()
        profile_id = quality_profile_id or resolved.radarr_default_quality_profile_id
        root_folder = resolved.radarr_default_root_folder
        if not profile_id or not root_folder:
            add_error = (
                "Set a default root folder and quality profile in Settings first."
            )
        else:
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
                add_error = "Could not add the movie to Radarr. Please try again."

    context: dict[str, object] = {"movie": movie, "add_error": add_error}

    if source == "modal":
        if add_error is None:
            # Success: close the modal by emptying #modal, and update the grid
            # card out-of-band. The OOB <article> is pulled from the body, so the
            # retargeted innerHTML swap leaves #modal empty.
            response = templates.TemplateResponse(
                request, "partials/movie_card.html", {"movie": movie, "oob": True}
            )
            response.headers["HX-Retarget"] = "#modal"
            response.headers["HX-Reswap"] = "innerHTML"
            return response
        # Failure: keep the modal open, re-render its controls with the error.
        return templates.TemplateResponse(
            request, "partials/movie_add_modal.html", context
        )

    # Card source: swap the whole card so its poster greys out on success.
    return templates.TemplateResponse(request, "partials/movie_card.html", context)


@router.get("/movies/{movie_id}/modal", response_class=HTMLResponse)
def movie_modal(
    request: Request,
    movie_id: int,
    session: Session = Depends(get_session),
    service: MovieService | None = Depends(get_movie_service),
    radarr: RadarrService | None = Depends(get_radarr_service),
) -> HTMLResponse:
    """Return the synopsis modal partial for a movie (HTMX endpoint).

    Fetches TMDB details (overview, release date, trailer) for the modal and
    merges Radarr status so the modal can offer Add / Add + Search just like a
    card. Fails soft: an unconfigured TMDB key or a Radarr outage renders the
    modal with an inline error / no status rather than crashing (PRD §15).
    """
    resolved = SettingsService(session).resolve()
    context: dict[str, object] = {
        "detail": None,
        "movie": None,
        "error": None,
        "quality_profiles": _quality_profiles(radarr),
        "default_quality_profile_id": resolved.radarr_default_quality_profile_id,
    }

    if service is None:
        context["error"] = "TMDB API key is not configured."
        return templates.TemplateResponse(
            request, "partials/movie_modal.html", context
        )

    try:
        detail = service.details(movie_id)
    except httpx.HTTPError as exc:
        logger.warning(
            "TMDB details failed: %s (movie_id=%s)", type(exc).__name__, movie_id
        )
        context["error"] = "Could not load movie details right now."
        return templates.TemplateResponse(
            request, "partials/movie_modal.html", context
        )

    # A Movie carries the Radarr status + addable state for the shared controls.
    movie = Movie(
        id=detail.id,
        title=detail.title,
        year=detail.year,
        rating=detail.rating,
        poster_url=detail.poster_url,
    )
    _annotate_radarr([movie], radarr, list_id="modal", page=movie_id)
    context["detail"] = detail
    context["movie"] = movie
    return templates.TemplateResponse(request, "partials/movie_modal.html", context)


@router.get("/health")
def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})
